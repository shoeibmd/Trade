"""
Auto-Trading Controller for Astraea MT5.
Orchestrates background polling, market data retrieval, signal evaluation,
risk checking, and paper/demo execution routing with safety controls.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from trading.models import SignalType, TradingSignal
from trading.mt5_connection import MT5Connection, ConnectionState
from trading.mt5_data import MT5DataEngine
from trading.forex_adapter import KronosAdapter
from trading.indicators import TechnicalIndicatorEngine
from trading.signal_engine import SignalEngine, SignalResult
from trading.risk_manager import RiskManager, RiskDecision, AccountState, SymbolSpecification
from trading.paper_execution import PaperExecutionEngine, PaperAccountState
from trading.mt5_demo_execution import MT5DemoExecutionEngine

logger = logging.getLogger("AstraeaMT5.AutoTrader")


@dataclass
class AutoTraderConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M5"
    poll_interval_sec: float = 10.0
    system_mode: str = "PAPER"
    demo_trading_enabled: bool = False
    live_trading_enabled: bool = False
    max_risk_percent: float = 1.0
    manual_lot_size: Optional[float] = None


class AutoTradingController:
    """
    Manages automated background trading loops safely.
    Never starts automatically upon application launch or reconnection.
    """

    def __init__(
        self,
        config: Optional[AutoTraderConfig] = None,
        connection: Optional[MT5Connection] = None,
        data_engine: Optional[MT5DataEngine] = None,
        forex_adapter: Optional[KronosAdapter] = None,
        indicator_engine: Optional[TechnicalIndicatorEngine] = None,
        signal_engine: Optional[SignalEngine] = None,
        risk_manager: Optional[RiskManager] = None,
        paper_engine: Optional[PaperExecutionEngine] = None,
        demo_engine: Optional[MT5DemoExecutionEngine] = None,
    ):
        self.config = config or AutoTraderConfig()
        self.connection = connection or MT5Connection()
        self.data_engine = data_engine or MT5DataEngine(self.connection)
        self.forex_adapter = forex_adapter or KronosAdapter()
        self.indicator_engine = indicator_engine or TechnicalIndicatorEngine()
        self.signal_engine = signal_engine or SignalEngine()
        self.risk_manager = risk_manager or RiskManager()
        self.paper_engine = paper_engine or PaperExecutionEngine()
        self.demo_engine = demo_engine or MT5DemoExecutionEngine(
            system_mode=self.config.system_mode,
            demo_trading_enabled=self.config.demo_trading_enabled,
            live_trading_enabled=False,
            mt5_connection=self.connection,
        )

        self.is_running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.stop_requested: bool = False
        self.last_poll_time: Optional[datetime] = None
        self.last_signal: Optional[SignalResult] = None
        self.last_risk_decision: Optional[RiskDecision] = None
        self.last_error: Optional[str] = None
        self.poll_count: int = 0

    def start_trading(self) -> Tuple[bool, str]:
        """
        Starts the automated trading background loop.
        Requires explicit user invocation. Never auto-starts.
        """
        if self.is_running:
            return False, "Auto-Trading Controller is already running."

        # Safety Check: Enforce PAPER mode or explicit DEMO configuration
        if self.config.system_mode.upper() == "LIVE" or self.config.live_trading_enabled:
            msg = "SAFETY REJECTED: LIVE trading is strictly disabled in Astraea MT5."
            logger.error(msg)
            return False, msg

        self.is_running = True
        self.stop_requested = False
        self.last_error = None

        self.thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.thread.start()

        msg = f"Auto-Trading started for {self.config.symbol} ({self.config.timeframe}) in {self.config.system_mode} mode."
        logger.info(msg)
        return True, msg

    def stop_trading(self) -> Tuple[bool, str]:
        """
        Stops the automated trading background loop immediately.
        Does NOT automatically close open positions.
        """
        if not self.is_running:
            return False, "Auto-Trading Controller is not running."

        self.stop_requested = True
        self.is_running = False

        msg = f"Auto-Trading stopped for {self.config.symbol}. Open positions remain active."
        logger.info(msg)
        return True, msg

    def validate_manual_lot_size(
        self, lot_size: float, symbol_spec: Optional[SymbolSpecification] = None
    ) -> Tuple[bool, str]:
        """
        Validates manual lot size against broker volume constraints.
        Reject trade if any check fails. Never silently increase lot size.
        """
        spec = symbol_spec or SymbolSpecification(symbol=self.config.symbol)

        if lot_size < spec.min_volume:
            return False, f"Lot size {lot_size} is below minimum broker volume {spec.min_volume}."
        if lot_size > spec.max_volume:
            return False, f"Lot size {lot_size} exceeds maximum broker volume {spec.max_volume}."

        # Verify step alignment
        step_diff = round((lot_size - spec.min_volume) % spec.volume_step, 6)
        if step_diff != 0 and abs(step_diff - spec.volume_step) > 1e-5:
            return False, f"Lot size {lot_size} does not align with broker volume step {spec.volume_step}."

        return True, f"Lot size {lot_size} is valid."

    def _trading_loop(self) -> None:
        """Background thread execution loop."""
        symbol_spec = SymbolSpecification(symbol=self.config.symbol)

        while not self.stop_requested:
            try:
                self.poll_count += 1
                self.last_poll_time = datetime.now()

                # 1. Fetch closed bar history
                bars_df, val_res = self.data_engine.get_closed_bars(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                    count=400,
                )

                if val_res.is_valid and bars_df is not None:
                    # 2. Compute technical indicators
                    ind_df = self.indicator_engine.calculate_all_indicators(bars_df)

                    # 3. Generate foundation model forecast
                    pred_res, err = self.forex_adapter.predict_forecast(
                        bars_df,
                        symbol=self.config.symbol,
                        timeframe=self.config.timeframe,
                    )

                    # 4. Evaluate signal engine
                    sig_res = self.signal_engine.evaluate_signal(
                        ind_df,
                        forecast=pred_res,
                        symbol=self.config.symbol,
                        timeframe=self.config.timeframe,
                    )
                    self.last_signal = sig_res

                    # 5. Evaluate risk manager if signal is BUY/SELL
                    if sig_res.signal in (SignalType.BUY, SignalType.SELL):
                        account_state = AccountState(
                            equity=self.paper_engine.account_state.equity,
                            balance=self.paper_engine.account_state.balance,
                            start_of_day_equity=self.paper_engine.account_state.start_of_day_equity,
                            open_positions_count=1 if self.paper_engine.account_state.open_position else 0,
                            realized_daily_pnl=self.paper_engine.account_state.daily_pnl,
                        )

                        risk_dec = self.risk_manager.evaluate_risk(
                            sig_res,
                            account_state,
                            symbol_spec,
                            indicator_df=ind_df,
                        )
                        self.last_risk_decision = risk_dec

                        # Manual lot size override validation
                        if self.config.manual_lot_size:
                            ok_lot, lot_msg = self.validate_manual_lot_size(
                                self.config.manual_lot_size, symbol_spec
                            )
                            if ok_lot and risk_dec.approved:
                                risk_dec.calculated_lot_size = self.config.manual_lot_size
                            elif not ok_lot:
                                risk_dec.approved = False
                                risk_dec.reason = f"REJECTED: Manual Lot Validation Failed: {lot_msg}"

                        # 6. Execute via PAPER mode non-order gate or DEMO mode
                        if risk_dec.approved:
                            if self.config.system_mode.upper() == "PAPER":
                                # Strict PAPER Non-Order Gate: In-memory simulation ONLY
                                self.paper_engine.execute_risk_decision(risk_dec, sig_res, symbol_spec)
                                logger.info(f"PAPER order executed simulated fill for {self.config.symbol}.")
                            elif self.config.system_mode.upper() == "DEMO" and self.config.demo_trading_enabled:
                                self.demo_engine.execute_demo_order(sig_res, risk_dec, symbol_spec)

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error in Auto-Trading loop: {e}")

            # Sleep for configured interval
            time.sleep(self.config.poll_interval_sec)

        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status dictionary for Web UI dashboard."""
        return {
            "is_running": self.is_running,
            "system_mode": self.config.system_mode,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "poll_interval_sec": self.config.poll_interval_sec,
            "poll_count": self.poll_count,
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "last_signal": self.last_signal.signal.value if self.last_signal else "NONE",
            "last_signal_score": self.last_signal.signal_score if self.last_signal else 0.0,
            "last_risk_approved": self.last_risk_decision.approved if self.last_risk_decision else False,
            "last_error": self.last_error,
            "paper_account": {
                "balance": self.paper_engine.account_state.balance,
                "equity": self.paper_engine.account_state.equity,
                "has_open_position": self.paper_engine.account_state.open_position is not None,
            },
        }
