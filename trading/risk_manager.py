"""
Astraea MT5 Risk Management & Position Sizing Engine.
Evaluates validated SignalResult decisions and calculates dynamic position sizing,
stop-loss levels, take-profit targets (1.5R), broker constraint rounding, and risk limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd
import yaml

from trading.models import SignalType
from trading.signal_engine import SignalResult, StructureState

logger = logging.getLogger("AstraeaMT5.RiskManager")


@dataclass
class SymbolSpecification:
    symbol: str = "EURUSD"
    digits: int = 5
    point: float = 0.00001
    tick_size: float = 0.00001
    tick_value: float = 1.0  # Monetary value of 1 tick per 1.0 standard lot in account currency
    contract_size: float = 100000.0  # 1 standard lot = 100,000 units
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01


@dataclass
class AccountState:
    equity: float = 10000.0
    balance: float = 10000.0
    start_of_day_equity: float = 10000.0
    open_positions_count: int = 0
    realized_daily_pnl: float = 0.0
    unrealized_daily_pnl: float = 0.0
    consecutive_losses: int = 0
    date_timestamp: Optional[date] = None


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    symbol: str
    direction: Optional[SignalType]
    entry_price: float
    stop_loss: float
    take_profit: float
    stop_distance: float
    risk_amount: float
    risk_percent: float
    calculated_lot_size: float
    risk_reward_ratio: float
    account_equity: float
    daily_loss_percent: float
    consecutive_losses: int
    open_positions: int
    config_values: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class RiskManager:
    """
    Risk Engine evaluating SignalResult decisions against account state and broker constraints.
    Calculates dynamic lot size and SL/TP without placing orders.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        risk_per_trade_percent: float = 1.0,
        max_open_positions: int = 1,
        max_daily_loss_percent: float = 3.0,
        max_consecutive_losses: int = 3,
        reward_risk_ratio: float = 1.5,
    ):
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_open_positions = max_open_positions
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_consecutive_losses = max_consecutive_losses
        self.reward_risk_ratio = reward_risk_ratio

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "risk" in cfg:
                        rcfg = cfg["risk"]
                        self.risk_per_trade_percent = float(rcfg.get("risk_per_trade_percent", self.risk_per_trade_percent))
                        self.max_open_positions = int(rcfg.get("max_open_positions", self.max_open_positions))
                        self.max_daily_loss_percent = float(rcfg.get("max_daily_loss_percent", self.max_daily_loss_percent))
                        self.max_consecutive_losses = int(rcfg.get("max_consecutive_losses", self.max_consecutive_losses))
                        self.reward_risk_ratio = float(rcfg.get("reward_risk_ratio", self.reward_risk_ratio))
            except Exception as e:
                logger.error(f"Failed to load risk config from {config_path}: {e}")

    def evaluate_risk(
        self,
        signal_result: SignalResult,
        account_state: AccountState,
        symbol_spec: SymbolSpecification,
        indicator_df: Optional[pd.DataFrame] = None,
    ) -> RiskDecision:
        """
        Evaluates risk for a SignalResult and returns a RiskDecision.
        """
        now = datetime.now()
        config_snapshot = {
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "max_open_positions": self.max_open_positions,
            "max_daily_loss_percent": self.max_daily_loss_percent,
            "max_consecutive_losses": self.max_consecutive_losses,
            "reward_risk_ratio": self.reward_risk_ratio,
        }

        # 1. Reject NO_TRADE or missing/HOLD signals
        if signal_result is None or signal_result.signal in (SignalType.HOLD, None):
            return RiskDecision(
                approved=False,
                reason="REJECTED: Signal is NO_TRADE / HOLD.",
                symbol=signal_result.symbol if signal_result else symbol_spec.symbol,
                direction=None,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity if account_state else 0.0,
                daily_loss_percent=self._calculate_daily_loss_percent(account_state),
                consecutive_losses=account_state.consecutive_losses if account_state else 0,
                open_positions=account_state.open_positions_count if account_state else 0,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 2. Account state validation
        if account_state is None or account_state.equity <= 0:
            return RiskDecision(
                approved=False,
                reason="REJECTED: Invalid or non-positive account equity.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity if account_state else 0.0,
                daily_loss_percent=0.0,
                consecutive_losses=account_state.consecutive_losses if account_state else 0,
                open_positions=account_state.open_positions_count if account_state else 0,
                config_values=config_snapshot,
                timestamp=now,
            )

        daily_loss_pct = self._calculate_daily_loss_percent(account_state)

        # 3. Maximum open positions check
        if account_state.open_positions_count >= self.max_open_positions:
            return RiskDecision(
                approved=False,
                reason=f"REJECTED: Maximum open positions limit reached ({account_state.open_positions_count} >= {self.max_open_positions}).",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 4. Daily loss limit check
        if daily_loss_pct >= self.max_daily_loss_percent:
            return RiskDecision(
                approved=False,
                reason=f"REJECTED: Maximum daily loss limit reached ({daily_loss_pct:.2f}% >= {self.max_daily_loss_percent:.2f}%).",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 5. Consecutive loss limit check
        if account_state.consecutive_losses >= self.max_consecutive_losses:
            return RiskDecision(
                approved=False,
                reason=f"REJECTED: Maximum consecutive loss limit reached ({account_state.consecutive_losses} >= {self.max_consecutive_losses}).",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 6. Extract Entry Price and ATR
        snap = signal_result.indicator_snapshot or {}
        entry_price = snap.get("close")
        atr_14 = snap.get("atr_14")

        if entry_price is None or entry_price <= 0:
            return RiskDecision(
                approved=False,
                reason="REJECTED: Invalid or missing entry price in indicator snapshot.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        if atr_14 is None or pd.isna(atr_14) or atr_14 <= 0:
            return RiskDecision(
                approved=False,
                reason="REJECTED: Missing or invalid ATR (atr_14) for stop-loss calculation.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=entry_price,
                stop_loss=0.0,
                take_profit=0.0,
                stop_distance=0.0,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 7. Calculate Stop Loss (SL) & Take Profit (TP)
        sl, tp, stop_dist = self._calculate_sl_tp(
            direction=signal_result.signal,
            entry_price=entry_price,
            atr_14=float(atr_14),
            symbol_spec=symbol_spec,
            indicator_df=indicator_df,
        )

        if stop_dist <= 0:
            return RiskDecision(
                approved=False,
                reason="REJECTED: Calculated stop distance is zero or negative.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                stop_distance=stop_dist,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=0.0,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        reward_dist = abs(tp - entry_price)
        rr_ratio = reward_dist / stop_dist

        if rr_ratio < self.reward_risk_ratio - 1e-4:
            return RiskDecision(
                approved=False,
                reason=f"REJECTED: Risk/reward ratio {rr_ratio:.2f} below target {self.reward_risk_ratio:.2f}.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                stop_distance=stop_dist,
                risk_amount=0.0,
                risk_percent=0.0,
                calculated_lot_size=0.0,
                risk_reward_ratio=rr_ratio,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # 8. Dynamic Lot Size Calculation
        risk_amount = account_state.equity * (self.risk_per_trade_percent / 100.0)

        # Loss per 1 standard lot = (stop_distance / tick_size) * tick_value
        ticks_in_stop = stop_dist / symbol_spec.tick_size
        monetary_loss_per_lot = ticks_in_stop * symbol_spec.tick_value

        if monetary_loss_per_lot <= 0:
            return RiskDecision(
                approved=False,
                reason="REJECTED: Invalid monetary loss per lot calculation.",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                stop_distance=stop_dist,
                risk_amount=risk_amount,
                risk_percent=self.risk_per_trade_percent,
                calculated_lot_size=0.0,
                risk_reward_ratio=rr_ratio,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        raw_lot_size = risk_amount / monetary_loss_per_lot
        rounded_lot_size = self._apply_broker_lot_constraints(raw_lot_size, symbol_spec)

        if rounded_lot_size < symbol_spec.volume_min:
            return RiskDecision(
                approved=False,
                reason=f"REJECTED: Calculated lot size ({raw_lot_size:.4f} lots) below broker minimum ({symbol_spec.volume_min} lots).",
                symbol=signal_result.symbol,
                direction=signal_result.signal,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                stop_distance=stop_dist,
                risk_amount=risk_amount,
                risk_percent=self.risk_per_trade_percent,
                calculated_lot_size=rounded_lot_size,
                risk_reward_ratio=rr_ratio,
                account_equity=account_state.equity,
                daily_loss_percent=daily_loss_pct,
                consecutive_losses=account_state.consecutive_losses,
                open_positions=account_state.open_positions_count,
                config_values=config_snapshot,
                timestamp=now,
            )

        # Approved Risk Decision
        return RiskDecision(
            approved=True,
            reason=f"APPROVED: Risk decision passed all constraints ({rounded_lot_size:.2f} lots, SL: {sl:.5f}, TP: {tp:.5f}, RR: {rr_ratio:.2f}).",
            symbol=signal_result.symbol,
            direction=signal_result.signal,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            stop_distance=stop_dist,
            risk_amount=risk_amount,
            risk_percent=self.risk_per_trade_percent,
            calculated_lot_size=rounded_lot_size,
            risk_reward_ratio=rr_ratio,
            account_equity=account_state.equity,
            daily_loss_percent=daily_loss_pct,
            consecutive_losses=account_state.consecutive_losses,
            open_positions=account_state.open_positions_count,
            config_values=config_snapshot,
            timestamp=now,
        )

    def _calculate_daily_loss_percent(self, account_state: AccountState) -> float:
        """
        Calculates daily loss percentage relative to starting-of-day equity.
        Formula: max(0.0, ((start_of_day_equity - current_equity) / start_of_day_equity) * 100.0)
        Realized PnL is also tracked: if start_of_day_equity <= 0, uses balance - (realized_daily_pnl + unrealized_daily_pnl).
        """
        if account_state is None:
            return 0.0

        base_equity = account_state.start_of_day_equity
        if base_equity <= 0:
            base_equity = account_state.balance - account_state.realized_daily_pnl

        if base_equity <= 0:
            return 0.0

        daily_loss_currency = base_equity - account_state.equity
        if daily_loss_currency <= 0:
            return 0.0

        return (daily_loss_currency / base_equity) * 100.0

    def _calculate_sl_tp(
        self,
        direction: SignalType,
        entry_price: float,
        atr_14: float,
        symbol_spec: SymbolSpecification,
        indicator_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculates protective Stop Loss (SL) and Take Profit (TP) based on ATR 14 and market structure.
        """
        atr_multiplier = 1.5
        stop_dist = max(atr_14 * atr_multiplier, symbol_spec.point * 50)  # Min 5 pips

        # Refine SL using recent swing low/high if available
        if indicator_df is not None and len(indicator_df) >= 10:
            recent_window = indicator_df.iloc[-10:]
            if direction == SignalType.BUY:
                swing_low = float(recent_window["low"].min())
                structure_sl_dist = entry_price - swing_low + (symbol_spec.point * 10)  # Add 1 pip buffer
                if structure_sl_dist > 0:
                    stop_dist = max(stop_dist, structure_sl_dist)
            elif direction == SignalType.SELL:
                swing_high = float(recent_window["high"].max())
                structure_sl_dist = swing_high - entry_price + (symbol_spec.point * 10)  # Add 1 pip buffer
                if structure_sl_dist > 0:
                    stop_dist = max(stop_dist, structure_sl_dist)

        stop_dist = round(stop_dist, symbol_spec.digits)

        if direction == SignalType.BUY:
            sl = round(entry_price - stop_dist, symbol_spec.digits)
            tp = round(entry_price + (stop_dist * self.reward_risk_ratio), symbol_spec.digits)
        else:  # SELL
            sl = round(entry_price + stop_dist, symbol_spec.digits)
            tp = round(entry_price - (stop_dist * self.reward_risk_ratio), symbol_spec.digits)

        return sl, tp, stop_dist

    def _apply_broker_lot_constraints(self, raw_lots: float, symbol_spec: SymbolSpecification) -> float:
        """
        Rounds raw lot size down to the nearest volume_step and enforces volume_min and volume_max.
        """
        if raw_lots <= 0:
            return 0.0

        step = symbol_spec.volume_step
        if step > 0:
            steps_count = int(raw_lots / step + 1e-9)
            constrained_lots = round(steps_count * step, 8)
        else:
            constrained_lots = raw_lots

        if constrained_lots > symbol_spec.volume_max:
            constrained_lots = symbol_spec.volume_max

        return round(constrained_lots, 4)
