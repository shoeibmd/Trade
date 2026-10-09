"""
Astraea MT5 Paper Trading & Simulation Engine.
Simulates complete position execution, lifecycle management, SL/TP monitoring,
P&L calculation, paper account state updates, and SQLite local persistence
without calling any real order placement function.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
import logging
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import yaml

from trading.models import SignalType
from trading.signal_engine import SignalResult
from trading.risk_manager import RiskDecision, AccountState, SymbolSpecification

logger = logging.getLogger("AstraeaMT5.PaperExecution")


@dataclass
class PaperPosition:
    position_id: str
    symbol: str
    timeframe: str
    direction: SignalType
    entry_timestamp: datetime
    entry_price: float
    lot_size: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    risk_percent: float
    signal_score: float
    signal_reasons: List[str] = field(default_factory=list)


@dataclass
class PaperTradeRecord:
    trade_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_timestamp: str
    entry_price: float
    exit_timestamp: str
    exit_price: float
    lot_size: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    risk_percent: float
    profit_loss: float
    exit_reason: str
    signal_score: float
    signal_reasons: str
    duration_seconds: float


@dataclass
class PaperAccountState:
    initial_balance: float = 10000.0
    balance: float = 10000.0
    equity: float = 10000.0
    start_of_day_equity: float = 10000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    open_position: Optional[PaperPosition] = None


class PaperExecutionEngine:
    """
    Paper Trading & Simulation Engine for Astraea MT5.
    Simulates paper execution from RiskDecision outputs and updates paper account state.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        db_path: Optional[str] = "data/paper_trades.db",
        initial_balance: float = 10000.0,
        spread_points: int = 0,
        slippage_points: int = 0,
    ):
        self.initial_balance = initial_balance
        self.spread_points = spread_points
        self.slippage_points = slippage_points
        self.db_path = db_path

        if config_path:
            self._load_config(config_path)

        self.account_state = PaperAccountState(
            initial_balance=self.initial_balance,
            balance=self.initial_balance,
            equity=self.initial_balance,
            start_of_day_equity=self.initial_balance,
        )
        self.closed_trades: List[PaperTradeRecord] = []

        if self.db_path:
            self._init_db()

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "paper" in cfg:
                        pcfg = cfg["paper"]
                        self.initial_balance = float(pcfg.get("initial_balance", self.initial_balance))
                        self.spread_points = int(pcfg.get("spread_points", self.spread_points))
                        self.slippage_points = int(pcfg.get("slippage_points", self.slippage_points))
            except Exception as e:
                logger.error(f"Failed to load paper config from {config_path}: {e}")

    def _init_db(self) -> None:
        if not self.db_path:
            return
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS paper_trades (
                        trade_id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_timestamp TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        exit_timestamp TEXT NOT NULL,
                        exit_price REAL NOT NULL,
                        lot_size REAL NOT NULL,
                        stop_loss REAL NOT NULL,
                        take_profit REAL NOT NULL,
                        risk_amount REAL NOT NULL,
                        risk_percent REAL NOT NULL,
                        profit_loss REAL NOT NULL,
                        exit_reason TEXT NOT NULL,
                        signal_score REAL NOT NULL,
                        signal_reasons TEXT NOT NULL,
                        duration_seconds REAL NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize paper trades SQLite database at {self.db_path}: {e}")

    def execute_risk_decision(
        self,
        risk_decision: RiskDecision,
        signal_result: SignalResult,
        symbol_spec: SymbolSpecification,
    ) -> Optional[PaperPosition]:
        """
        Executes a PaperPosition if risk_decision.approved is True and no open position exists.
        Returns the created PaperPosition or None if rejected.
        """
        if risk_decision is None or not risk_decision.approved:
            logger.info(f"Paper Execution: Risk decision rejected or None. Reason: {risk_decision.reason if risk_decision else 'None'}")
            return None

        if self.account_state.open_position is not None:
            logger.warning("Paper Execution: Cannot open new paper position; position already open.")
            return None

        # Entry Price calculation with optional spread/slippage adjustment
        entry_price = risk_decision.entry_price
        spread_offset = self.spread_points * symbol_spec.point
        slippage_offset = self.slippage_points * symbol_spec.point

        if risk_decision.direction == SignalType.BUY:
            actual_entry = entry_price + spread_offset + slippage_offset
        else:  # SELL
            actual_entry = entry_price - spread_offset - slippage_offset

        pos = PaperPosition(
            position_id=str(uuid.uuid4()),
            symbol=risk_decision.symbol,
            timeframe=signal_result.timeframe if signal_result else "M5",
            direction=risk_decision.direction,
            entry_timestamp=risk_decision.timestamp,
            entry_price=round(actual_entry, symbol_spec.digits),
            lot_size=risk_decision.calculated_lot_size,
            stop_loss=risk_decision.stop_loss,
            take_profit=risk_decision.take_profit,
            risk_amount=risk_decision.risk_amount,
            risk_percent=risk_decision.risk_percent,
            signal_score=signal_result.signal_score if signal_result else 0.0,
            signal_reasons=signal_result.reasons if signal_result else [],
        )

        self.account_state.open_position = pos
        logger.info(f"Paper Position Opened: ID={pos.position_id}, {pos.direction.value} {pos.lot_size} lots @ {pos.entry_price:.5f}")
        return pos

    def process_subsequent_bars(
        self,
        new_bars_df: pd.DataFrame,
        symbol_spec: SymbolSpecification,
    ) -> Optional[PaperTradeRecord]:
        """
        Monitors subsequent closed bars to check if open position hits Stop Loss (SL) or Take Profit (TP).
        Handles same-candle SL/TP ambiguity conservatively by prioritizing SL hit over TP hit.
        Returns PaperTradeRecord if trade closed, or None if still open.
        """
        pos = self.account_state.open_position
        if pos is None or new_bars_df is None or len(new_bars_df) == 0:
            return None

        for _, bar in new_bars_df.iterrows():
            bar_time = bar["timestamps"] if "timestamps" in bar else datetime.now()
            high = float(bar["high"])
            low = float(bar["low"])

            sl_hit = False
            tp_hit = False

            if pos.direction == SignalType.BUY:
                if low <= pos.stop_loss:
                    sl_hit = True
                if high >= pos.take_profit:
                    tp_hit = True
            elif pos.direction == SignalType.SELL:
                if high >= pos.stop_loss:
                    sl_hit = True
                if low <= pos.take_profit:
                    tp_hit = True

            if sl_hit or tp_hit:
                # Same-candle ambiguity resolution: PESSIMISTIC/CONSERVATIVE RULE (SL precedes TP)
                if sl_hit and tp_hit:
                    exit_reason = "STOP_LOSS (Same-candle ambiguity: SL prioritized)"
                    exit_price = pos.stop_loss
                elif sl_hit:
                    exit_reason = "STOP_LOSS"
                    exit_price = pos.stop_loss
                else:
                    exit_reason = "TAKE_PROFIT"
                    exit_price = pos.take_profit

                return self._close_paper_position(
                    pos=pos,
                    exit_price=exit_price,
                    exit_timestamp=bar_time,
                    exit_reason=exit_reason,
                    symbol_spec=symbol_spec,
                )

        return None

    def _close_paper_position(
        self,
        pos: PaperPosition,
        exit_price: float,
        exit_timestamp: datetime,
        exit_reason: str,
        symbol_spec: SymbolSpecification,
    ) -> PaperTradeRecord:
        """
        Closes paper position, computes P&L using symbol specs, updates paper account state,
        and logs record to SQLite database.
        """
        pnl_currency = self.calculate_pnl(
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            lot_size=pos.lot_size,
            symbol_spec=symbol_spec,
        )

        duration = (exit_timestamp - pos.entry_timestamp).total_seconds()
        if duration < 0:
            duration = 0.0

        trade_record = PaperTradeRecord(
            trade_id=pos.position_id,
            symbol=pos.symbol,
            timeframe=pos.timeframe,
            direction=pos.direction.value if isinstance(pos.direction, SignalType) else str(pos.direction),
            entry_timestamp=pos.entry_timestamp.isoformat(),
            entry_price=pos.entry_price,
            exit_timestamp=exit_timestamp.isoformat(),
            exit_price=exit_price,
            lot_size=pos.lot_size,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            risk_amount=pos.risk_amount,
            risk_percent=pos.risk_percent,
            profit_loss=round(pnl_currency, 2),
            exit_reason=exit_reason,
            signal_score=pos.signal_score,
            signal_reasons=" | ".join(pos.signal_reasons),
            duration_seconds=duration,
        )

        # Update Paper Account State
        self.account_state.balance += pnl_currency
        self.account_state.equity = self.account_state.balance
        self.account_state.realized_pnl += pnl_currency
        self.account_state.daily_pnl += pnl_currency
        self.account_state.total_trades += 1

        if pnl_currency > 0:
            self.account_state.winning_trades += 1
            self.account_state.gross_profit += pnl_currency
            self.account_state.consecutive_losses = 0
        else:
            self.account_state.losing_trades += 1
            self.account_state.gross_loss += abs(pnl_currency)
            self.account_state.consecutive_losses += 1

        self.account_state.open_position = None
        self.closed_trades.append(trade_record)

        if self.db_path:
            self._save_trade_to_db(trade_record)

        logger.info(f"Paper Trade Closed: ID={trade_record.trade_id}, PnL=${pnl_currency:+.2f}, Reason={exit_reason}")
        return trade_record

    @staticmethod
    def calculate_pnl(
        direction: SignalType,
        entry_price: float,
        exit_price: float,
        lot_size: float,
        symbol_spec: SymbolSpecification,
    ) -> float:
        """
        Calculates account currency P&L from price movement and symbol specification.
        BUY PnL: ((exit_price - entry_price) / tick_size) * tick_value * lot_size
        SELL PnL: ((entry_price - exit_price) / tick_size) * tick_value * lot_size
        """
        if symbol_spec.tick_size <= 0:
            return 0.0

        if direction == SignalType.BUY:
            price_delta = exit_price - entry_price
        else:  # SELL
            price_delta = entry_price - exit_price

        ticks = price_delta / symbol_spec.tick_size
        pnl = ticks * symbol_spec.tick_value * lot_size
        return pnl

    def get_risk_account_state(self) -> AccountState:
        """
        Converts internal PaperAccountState to AccountState for RiskManager consumption.
        """
        return AccountState(
            equity=self.account_state.equity,
            balance=self.account_state.balance,
            start_of_day_equity=self.account_state.start_of_day_equity,
            open_positions_count=1 if self.account_state.open_position is not None else 0,
            realized_daily_pnl=self.account_state.daily_pnl,
            unrealized_daily_pnl=0.0,
            consecutive_losses=self.account_state.consecutive_losses,
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Returns basic Paper Trading Simulation statistics.
        """
        total = self.account_state.total_trades
        wins = self.account_state.winning_trades
        losses = self.account_state.losing_trades
        win_rate = (wins / total * 100.0) if total > 0 else 0.0
        avg_trade = (self.account_state.realized_pnl / total) if total > 0 else 0.0

        return {
            "type": "PAPER SIMULATION RESULT",
            "initial_balance": self.account_state.initial_balance,
            "current_balance": self.account_state.balance,
            "net_pnl": self.account_state.realized_pnl,
            "total_trades": total,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate_pct": round(win_rate, 2),
            "gross_profit": round(self.account_state.gross_profit, 2),
            "gross_loss": round(self.account_state.gross_loss, 2),
            "average_trade_pnl": round(avg_trade, 2),
            "consecutive_losses": self.account_state.consecutive_losses,
        }

    def _save_trade_to_db(self, record: PaperTradeRecord) -> None:
        if not self.db_path:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO paper_trades (
                        trade_id, symbol, timeframe, direction, entry_timestamp, entry_price,
                        exit_timestamp, exit_price, lot_size, stop_loss, take_profit,
                        risk_amount, risk_percent, profit_loss, exit_reason, signal_score,
                        signal_reasons, duration_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.trade_id, record.symbol, record.timeframe, record.direction,
                    record.entry_timestamp, record.entry_price, record.exit_timestamp,
                    record.exit_price, record.lot_size, record.stop_loss, record.take_profit,
                    record.risk_amount, record.risk_percent, record.profit_loss,
                    record.exit_reason, record.signal_score, record.signal_reasons,
                    record.duration_seconds
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist paper trade {record.trade_id} to SQLite DB: {e}")
