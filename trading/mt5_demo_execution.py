"""
Astraea MT5 Demo Trading Execution Engine.
Handles MetaTrader 5 demo order placement, account verification, and safety controls.
Includes 9 strict safety gates to isolate paper trading from demo trading,
enforce demo account verification via MT5 account metadata, reject real-money accounts,
prevent duplicate orders, and manage order results without exposing credentials in logs.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from trading.models import SignalType
from trading.signal_engine import SignalResult
from trading.risk_manager import RiskDecision, RiskManager, SymbolSpecification, AccountState
from trading.mt5_connection import MT5Connection, ConnectionState

logger = logging.getLogger("AstraeaMT5.DemoExecution")

# Account Trade Modes (MT5 Constants)
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2


@dataclass
class DemoAccountInfo:
    login: int
    trade_mode: int
    trade_mode_str: str
    is_demo: bool
    balance: float
    equity: float
    currency: str
    server: str
    company: str


@dataclass
class DemoOrderResult:
    success: bool
    reason: str
    ticket: Optional[int] = None
    symbol: str = ""
    direction: Optional[SignalType] = None
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    retcode: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class MT5DemoExecutionEngine:
    """
    MT5 Demo Execution Engine implementing 9 safety gates to execute orders
    ONLY on verified demo accounts when explicitly configured.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        mt5_connection: Optional[MT5Connection] = None,
        risk_manager: Optional[RiskManager] = None,
        symbol_spec: Optional[SymbolSpecification] = None,
        system_mode: str = "PAPER",
        demo_trading_enabled: bool = False,
        live_trading_enabled: bool = False,
        verify_demo_account: bool = True,
    ):
        self.system_mode = system_mode
        self.demo_trading_enabled = demo_trading_enabled
        self.live_trading_enabled = live_trading_enabled
        self.verify_demo_account = verify_demo_account

        if config_path:
            self._load_config(config_path)

        self.mt5_connection = mt5_connection or MT5Connection()
        self.risk_manager = risk_manager or RiskManager()
        self.symbol_spec = symbol_spec or SymbolSpecification()

        self.executed_signal_ids: set = set()
        self.executed_tickets: List[int] = []

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg:
                        sys_cfg = cfg.get("system", {})
                        self.system_mode = sys_cfg.get("mode", self.system_mode)

                        safety_cfg = cfg.get("safety", {})
                        self.live_trading_enabled = safety_cfg.get(
                            "live_trading_enabled", self.live_trading_enabled
                        )

                        demo_cfg = cfg.get("demo", {})
                        self.demo_trading_enabled = demo_cfg.get(
                            "demo_trading_enabled", self.demo_trading_enabled
                        )
                        self.verify_demo_account = demo_cfg.get(
                            "verify_demo_account", self.verify_demo_account
                        )
            except Exception as e:
                logger.error(f"Failed to load demo execution config from {config_path}: {e}")

    def verify_account(self) -> Tuple[bool, Optional[DemoAccountInfo], str]:
        """
        Retrieves account metadata from MT5 and verifies if the account is a verified DEMO account.
        Fails closed (returns False) if account mode is REAL, UNKNOWN, or if verification fails.
        """
        if not self.mt5_connection or self.mt5_connection.state != ConnectionState.CONNECTED:
            return False, None, "REJECTED: MT5 connection is not connected."

        mt5 = self.mt5_connection.get_mt5_module()
        if mt5 is None:
            return False, None, "REJECTED: MT5 Python package is unavailable."

        acc_info = mt5.account_info()
        if acc_info is None:
            return False, None, "REJECTED: Failed to retrieve account_info from MT5 terminal."

        login = getattr(acc_info, "login", 0)
        trade_mode = getattr(acc_info, "trade_mode", -1)
        balance = getattr(acc_info, "balance", 0.0)
        equity = getattr(acc_info, "equity", 0.0)
        currency = getattr(acc_info, "currency", "USD")
        server = getattr(acc_info, "server", "UnknownServer")
        company = getattr(acc_info, "company", "UnknownCompany")

        trade_mode_str = "UNKNOWN"
        is_demo = False

        if trade_mode == ACCOUNT_TRADE_MODE_DEMO:
            trade_mode_str = "DEMO"
            is_demo = True
        elif trade_mode == ACCOUNT_TRADE_MODE_CONTEST:
            trade_mode_str = "CONTEST"
            is_demo = True
        elif trade_mode == ACCOUNT_TRADE_MODE_REAL:
            trade_mode_str = "REAL"
            is_demo = False

        demo_info = DemoAccountInfo(
            login=login,
            trade_mode=trade_mode,
            trade_mode_str=trade_mode_str,
            is_demo=is_demo,
            balance=balance,
            equity=equity,
            currency=currency,
            server=server,
            company=company,
        )

        # REJECT REAL ACCOUNTS ABSOLUTELY
        if trade_mode == ACCOUNT_TRADE_MODE_REAL:
            logger.critical(
                f"SAFETY BLOCK: MT5 Account {login} on {server} is a REAL MONEY account (trade_mode={trade_mode}). ALL DEMO ORDERS BLOCKED."
            )
            return False, demo_info, f"SAFETY BLOCK: Account {login} is a REAL MONEY account. Demo orders forbidden."

        if not is_demo:
            return False, demo_info, f"REJECTED: Account {login} trade mode '{trade_mode_str}' is not verified DEMO."

        return True, demo_info, f"VERIFIED: Demo Account {login} ({company} / {server}) confirmed."

    def execute_demo_order(
        self,
        signal_result: SignalResult,
        risk_decision: RiskDecision,
        symbol_spec: Optional[SymbolSpecification] = None,
    ) -> DemoOrderResult:
        """
        Executes a demo order on MT5 after evaluating 9 strict safety gates.
        """
        now = datetime.now()
        spec = symbol_spec or self.symbol_spec

        # GATE 1: System Mode Check
        if self.system_mode != "DEMO":
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 1 REJECTED: System mode is '{self.system_mode}' (must be 'DEMO').",
                symbol=signal_result.symbol if signal_result else spec.symbol,
                timestamp=now,
            )

        # GATE 2: Demo Enable Flag Check
        if not self.demo_trading_enabled:
            return DemoOrderResult(
                success=False,
                reason="SAFETY GATE 2 REJECTED: demo_trading_enabled is False.",
                symbol=signal_result.symbol if signal_result else spec.symbol,
                timestamp=now,
            )

        # GATE 3: Live Trading Safety Check (Must be False)
        if self.live_trading_enabled:
            return DemoOrderResult(
                success=False,
                reason="SAFETY GATE 3 REJECTED: live_trading_enabled is True. Live trading forbidden in Phase 11.",
                symbol=signal_result.symbol if signal_result else spec.symbol,
                timestamp=now,
            )

        # GATE 4: Verified Demo Account Metadata Check
        verified, demo_info, verify_msg = self.verify_account()
        if not verified or demo_info is None or not demo_info.is_demo:
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 4 REJECTED: Account verification failed: {verify_msg}",
                symbol=signal_result.symbol if signal_result else spec.symbol,
                timestamp=now,
            )

        # GATE 5: Signal & Risk Decision Approval Check
        if signal_result is None or signal_result.signal in (SignalType.HOLD, None):
            return DemoOrderResult(
                success=False,
                reason="SAFETY GATE 5 REJECTED: Signal is NO_TRADE / HOLD.",
                symbol=spec.symbol,
                timestamp=now,
            )

        if risk_decision is None or not risk_decision.approved:
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 5 REJECTED: RiskDecision not approved ({risk_decision.reason if risk_decision else 'None'}).",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                timestamp=now,
            )

        # GATE 6: SL/TP & Volume Bounds Validation
        if risk_decision.calculated_lot_size < spec.volume_min or risk_decision.calculated_lot_size > spec.volume_max:
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 6 REJECTED: Volume {risk_decision.calculated_lot_size} outside bounds [{spec.volume_min}, {spec.volume_max}].",
                symbol=risk_decision.symbol,
                direction=risk_decision.direction,
                volume=risk_decision.calculated_lot_size,
                timestamp=now,
            )

        if risk_decision.stop_loss <= 0 or risk_decision.take_profit <= 0:
            return DemoOrderResult(
                success=False,
                reason="SAFETY GATE 6 REJECTED: Invalid Stop Loss or Take Profit levels.",
                symbol=risk_decision.symbol,
                direction=risk_decision.direction,
                timestamp=now,
            )

        # GATE 7: Duplicate Signal & Order Protection
        sig_id = f"{signal_result.symbol}_{signal_result.timestamp.isoformat()}_{signal_result.signal.value}"
        if sig_id in self.executed_signal_ids:
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 7 REJECTED: Duplicate signal execution blocked ({sig_id}).",
                symbol=risk_decision.symbol,
                direction=risk_decision.direction,
                timestamp=now,
            )

        # GATE 8: MT5 Terminal Connection & Symbol Trading State Check
        mt5 = self.mt5_connection.get_mt5_module()
        if mt5 is None or self.mt5_connection.state != ConnectionState.CONNECTED:
            return DemoOrderResult(
                success=False,
                reason="SAFETY GATE 8 REJECTED: Disconnected MT5 terminal.",
                symbol=risk_decision.symbol,
                direction=risk_decision.direction,
                timestamp=now,
            )

        # GATE 9: Existing Open Positions / Risk Limit Re-check
        # Re-check active open positions from MT5
        positions = mt5.positions_get(symbol=risk_decision.symbol)
        if positions is not None and len(positions) >= self.risk_manager.max_open_positions:
            return DemoOrderResult(
                success=False,
                reason=f"SAFETY GATE 9 REJECTED: Active MT5 positions ({len(positions)}) >= max_open_positions ({self.risk_manager.max_open_positions}).",
                symbol=risk_decision.symbol,
                direction=risk_decision.direction,
                timestamp=now,
            )

        # ALL 9 SAFETY GATES PASSED -> PREPARE MT5 ORDER REQUEST
        symbol = risk_decision.symbol
        lot = risk_decision.calculated_lot_size
        direction = risk_decision.direction

        if direction == SignalType.BUY:
            order_type = getattr(mt5, "ORDER_TYPE_BUY", 0)
            price = mt5.symbol_info_tick(symbol).ask if hasattr(mt5, "symbol_info_tick") and mt5.symbol_info_tick(symbol) else risk_decision.entry_price
        else:  # SELL
            order_type = getattr(mt5, "ORDER_TYPE_SELL", 1)
            price = mt5.symbol_info_tick(symbol).bid if hasattr(mt5, "symbol_info_tick") and mt5.symbol_info_tick(symbol) else risk_decision.entry_price

        request = {
            "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": risk_decision.stop_loss,
            "tp": risk_decision.take_profit,
            "deviation": 20,
            "magic": 999888,
            "comment": "Astraea MT5 Demo Order",
            "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
            "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1),
        }

        logger.info(f"Submitting MT5 Demo Order: {direction.value} {lot} lots {symbol} @ {price:.5f} (SL: {risk_decision.stop_loss}, TP: {risk_decision.take_profit})")

        result = mt5.order_send(request)
        if result is None:
            return DemoOrderResult(
                success=False,
                reason="REJECTED: MT5 order_send returned None.",
                symbol=symbol,
                direction=direction,
                volume=lot,
                price=price,
                timestamp=now,
            )

        retcode = getattr(result, "retcode", -1)
        trade_retcode_done = getattr(mt5, "TRADE_RETCODE_DONE", 10009)

        if retcode == trade_retcode_done:
            ticket = getattr(result, "order", 0) or getattr(result, "deal", 0)
            self.executed_signal_ids.add(sig_id)
            if ticket:
                self.executed_tickets.append(ticket)

            logger.info(f"MT5 Demo Order Executed Successfully: Ticket #{ticket}, Symbol={symbol}, Lot={lot}")
            return DemoOrderResult(
                success=True,
                reason=f"SUCCESS: Demo order executed on MT5 (Ticket #{ticket}).",
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                volume=lot,
                price=price,
                sl=risk_decision.stop_loss,
                tp=risk_decision.take_profit,
                retcode=retcode,
                timestamp=now,
            )
        else:
            comment = getattr(result, "comment", f"Retcode {retcode}")
            logger.error(f"MT5 Demo Order Failed: Retcode={retcode}, Comment={comment}")
            return DemoOrderResult(
                success=False,
                reason=f"REJECTED: MT5 order_send failed (Retcode {retcode}: {comment}).",
                symbol=symbol,
                direction=direction,
                volume=lot,
                price=price,
                retcode=retcode,
                timestamp=now,
            )

    def reconcile_open_positions(self, symbol: str = "EURUSD") -> List[Dict[str, Any]]:
        """
        Reconciles open positions from MT5 terminal upon application restart.
        """
        mt5 = self.mt5_connection.get_mt5_module()
        if mt5 is None or self.mt5_connection.state != ConnectionState.CONNECTED:
            logger.warning("Cannot reconcile positions: MT5 terminal disconnected.")
            return []

        positions = mt5.positions_get(symbol=symbol)
        reconciled = []
        if positions:
            for p in positions:
                ticket = getattr(p, "ticket", 0)
                pos_dict = {
                    "ticket": ticket,
                    "symbol": getattr(p, "symbol", symbol),
                    "volume": getattr(p, "volume", 0.0),
                    "type": getattr(p, "type", 0),
                    "price_open": getattr(p, "price_open", 0.0),
                    "sl": getattr(p, "sl", 0.0),
                    "tp": getattr(p, "tp", 0.0),
                    "profit": getattr(p, "profit", 0.0),
                }
                reconciled.append(pos_dict)
                if ticket and ticket not in self.executed_tickets:
                    self.executed_tickets.append(ticket)

        logger.info(f"Reconciled {len(reconciled)} active positions from MT5 terminal for {symbol}.")
        return reconciled
