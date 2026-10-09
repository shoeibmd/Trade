"""
Astraea MT5 Position Management Engine.
Manages active position lifecycles including Break-Even stop-loss adjustments,
ATR-based trailing stop-loss management, and broker constraint rounding
without loosening risk or executing live real-money trades.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from trading.models import SignalType
from trading.risk_manager import SymbolSpecification
from trading.paper_execution import PaperPosition
from trading.mt5_demo_execution import MT5DemoExecutionEngine, DemoOrderResult
from trading.mt5_connection import MT5Connection, ConnectionState

logger = logging.getLogger("AstraeaMT5.PositionManager")


@dataclass
class PositionModificationResult:
    success: bool
    action: str  # "NO_ACTION", "BREAKEVEN_APPLIED", "TRAILING_STOP_UPDATED", "MODIFICATION_FAILED", "REJECTED"
    ticket: Optional[int] = None
    symbol: str = ""
    direction: Optional[SignalType] = None
    old_sl: float = 0.0
    new_sl: float = 0.0
    old_tp: float = 0.0
    new_tp: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PositionManager:
    """
    Position Management Engine for Astraea MT5.
    Monitors active positions, evaluates Break-Even and ATR Trailing Stop triggers,
    and submits modifications ONLY when risk is reduced or protected (SL never moves backward).
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        breakeven_r_multiple: float = 1.0,
        breakeven_offset_points: int = 10,
        trailing_stop_atr_multiplier: float = 1.5,
        trailing_stop_activation_r_multiple: float = 1.2,
        polling_interval_seconds: int = 5,
        demo_execution_engine: Optional[MT5DemoExecutionEngine] = None,
        symbol_spec: Optional[SymbolSpecification] = None,
    ):
        self.breakeven_r_multiple = breakeven_r_multiple
        self.breakeven_offset_points = breakeven_offset_points
        self.trailing_stop_atr_multiplier = trailing_stop_atr_multiplier
        self.trailing_stop_activation_r_multiple = trailing_stop_activation_r_multiple
        self.polling_interval_seconds = polling_interval_seconds

        if config_path:
            self._load_config(config_path)

        self.demo_execution_engine = demo_execution_engine
        self.symbol_spec = symbol_spec or SymbolSpecification()
        self.breakeven_applied_tickets: set = set()

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "position_management" in cfg:
                        pm = cfg["position_management"]
                        self.breakeven_r_multiple = float(pm.get("breakeven_r_multiple", self.breakeven_r_multiple))
                        self.breakeven_offset_points = int(pm.get("breakeven_offset_points", self.breakeven_offset_points))
                        self.trailing_stop_atr_multiplier = float(pm.get("trailing_stop_atr_multiplier", self.trailing_stop_atr_multiplier))
                        self.trailing_stop_activation_r_multiple = float(pm.get("trailing_stop_activation_r_multiple", self.trailing_stop_activation_r_multiple))
                        self.polling_interval_seconds = int(pm.get("polling_interval_seconds", self.polling_interval_seconds))
            except Exception as e:
                logger.error(f"Failed to load position management config from {config_path}: {e}")

    def evaluate_paper_position_management(
        self,
        paper_pos: PaperPosition,
        current_price: float,
        current_atr: float,
        symbol_spec: Optional[SymbolSpecification] = None,
    ) -> PositionModificationResult:
        """
        Evaluates position management for a PaperPosition.
        Moves stop loss to break-even or trails ATR stop WITHOUT calling broker APIs.
        STRICT NON-REGRESSION RULE: SL must NEVER move backward (increase risk).
        """
        now = datetime.now()
        spec = symbol_spec or self.symbol_spec

        if paper_pos is None:
            return PositionModificationResult(
                success=False, action="REJECTED", reason="REJECTED: Paper position is None.", timestamp=now
            )

        direction = paper_pos.direction
        entry = paper_pos.entry_price
        sl = paper_pos.stop_loss
        tp = paper_pos.take_profit
        stop_dist = abs(entry - sl)

        if stop_dist <= 0:
            return PositionModificationResult(
                success=False, action="REJECTED", symbol=paper_pos.symbol, direction=direction, old_sl=sl, new_sl=sl, reason="REJECTED: Initial stop distance is zero.", timestamp=now
            )

        offset_price = self.breakeven_offset_points * spec.point
        proposed_sl = sl
        action_type = "NO_ACTION"
        reason = "NO_ACTION: Current price does not trigger break-even or trailing stop adjustments."

        # 1. Evaluate Break-Even Trigger
        be_trigger_dist = stop_dist * self.breakeven_r_multiple
        is_be_applied = paper_pos.position_id in self.breakeven_applied_tickets

        if direction == SignalType.BUY:
            current_profit_dist = current_price - entry
            be_target_sl = round(entry + offset_price, spec.digits)

            if not is_be_applied and current_profit_dist >= be_trigger_dist:
                if be_target_sl > sl:
                    proposed_sl = be_target_sl
                    action_type = "BREAKEVEN_APPLIED"
                    reason = f"BREAKEVEN: BUY profit (+{current_profit_dist:.5f}) >= {self.breakeven_r_multiple}R ({be_trigger_dist:.5f}). SL moved to {be_target_sl:.5f}."

            # 2. Evaluate ATR Trailing Stop Trigger
            trail_activation_dist = stop_dist * self.trailing_stop_activation_r_multiple
            if current_profit_dist >= trail_activation_dist and current_atr > 0:
                trail_sl_dist = current_atr * self.trailing_stop_atr_multiplier
                trail_proposed_sl = round(current_price - trail_sl_dist, spec.digits)

                if trail_proposed_sl > proposed_sl:
                    proposed_sl = trail_proposed_sl
                    action_type = "TRAILING_STOP_UPDATED"
                    reason = f"TRAILING_STOP: BUY profit (+{current_profit_dist:.5f}) >= {self.trailing_stop_activation_r_multiple}R. Trailing SL moved to {proposed_sl:.5f}."

        else:  # SELL
            current_profit_dist = entry - current_price
            be_target_sl = round(entry - offset_price, spec.digits)

            if not is_be_applied and current_profit_dist >= be_trigger_dist:
                if be_target_sl < sl:
                    proposed_sl = be_target_sl
                    action_type = "BREAKEVEN_APPLIED"
                    reason = f"BREAKEVEN: SELL profit (+{current_profit_dist:.5f}) >= {self.breakeven_r_multiple}R ({be_trigger_dist:.5f}). SL moved to {be_target_sl:.5f}."

            # 2. Evaluate ATR Trailing Stop Trigger
            trail_activation_dist = stop_dist * self.trailing_stop_activation_r_multiple
            if current_profit_dist >= trail_activation_dist and current_atr > 0:
                trail_sl_dist = current_atr * self.trailing_stop_atr_multiplier
                trail_proposed_sl = round(current_price + trail_sl_dist, spec.digits)

                if trail_proposed_sl < proposed_sl:
                    proposed_sl = trail_proposed_sl
                    action_type = "TRAILING_STOP_UPDATED"
                    reason = f"TRAILING_STOP: SELL profit (+{current_profit_dist:.5f}) >= {self.trailing_stop_activation_r_multiple}R. Trailing SL moved to {proposed_sl:.5f}."

        # STRICT NON-REGRESSION RULE CHECK
        if direction == SignalType.BUY and proposed_sl < sl:
            logger.warning(f"SAFETY GUARD BLOCK: Proposed BUY SL ({proposed_sl:.5f}) < Current SL ({sl:.5f}). Modification blocked.")
            return PositionModificationResult(
                success=False, action="REJECTED", symbol=paper_pos.symbol, direction=direction, old_sl=sl, new_sl=sl, old_tp=tp, new_tp=tp, reason="SAFETY GUARD: Proposed SL increases risk for BUY position.", timestamp=now
            )
        elif direction == SignalType.SELL and proposed_sl > sl:
            logger.warning(f"SAFETY GUARD BLOCK: Proposed SELL SL ({proposed_sl:.5f}) > Current SL ({sl:.5f}). Modification blocked.")
            return PositionModificationResult(
                success=False, action="REJECTED", symbol=paper_pos.symbol, direction=direction, old_sl=sl, new_sl=sl, old_tp=tp, new_tp=tp, reason="SAFETY GUARD: Proposed SL increases risk for SELL position.", timestamp=now
            )

        if action_type != "NO_ACTION" and proposed_sl != sl:
            paper_pos.stop_loss = proposed_sl
            self.breakeven_applied_tickets.add(paper_pos.position_id)
            logger.info(f"Paper Position Modified ({paper_pos.position_id}): {action_type}, SL={proposed_sl:.5f}")
            return PositionModificationResult(
                success=True, action=action_type, symbol=paper_pos.symbol, direction=direction, old_sl=sl, new_sl=proposed_sl, old_tp=tp, new_tp=tp, reason=reason, timestamp=now
            )

        return PositionModificationResult(
            success=True, action="NO_ACTION", symbol=paper_pos.symbol, direction=direction, old_sl=sl, new_sl=sl, old_tp=tp, new_tp=tp, reason=reason, timestamp=now
        )

    def evaluate_and_modify_demo_position(
        self,
        ticket: int,
        symbol: str,
        direction: SignalType,
        entry_price: float,
        current_sl: float,
        current_tp: float,
        current_price: float,
        current_atr: float,
        symbol_spec: Optional[SymbolSpecification] = None,
    ) -> PositionModificationResult:
        """
        Evaluates and submits position modification to MT5 for a verified DEMO account position.
        Employs all Phase 11 safety gates and verifies account metadata.
        """
        now = datetime.now()
        spec = symbol_spec or self.symbol_spec

        if not self.demo_execution_engine:
            return PositionModificationResult(
                success=False, action="REJECTED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=current_sl, reason="REJECTED: Demo execution engine is None.", timestamp=now
            )

        # Evaluate safety gates
        if self.demo_execution_engine.system_mode != "DEMO" or not self.demo_execution_engine.demo_trading_enabled:
            return PositionModificationResult(
                success=False, action="REJECTED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=current_sl, reason="REJECTED: System is not configured for DEMO trading.", timestamp=now
            )

        verified, demo_info, verify_msg = self.demo_execution_engine.verify_account()
        if not verified or demo_info is None or not demo_info.is_demo:
            return PositionModificationResult(
                success=False, action="REJECTED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=current_sl, reason=f"REJECTED: Account verification failed: {verify_msg}", timestamp=now
            )

        # Calculate proposed SL using paper pos abstraction
        dummy_pos = PaperPosition(
            position_id=str(ticket),
            symbol=symbol,
            timeframe="M5",
            direction=direction,
            entry_timestamp=now,
            entry_price=entry_price,
            lot_size=0.1,
            stop_loss=current_sl,
            take_profit=current_tp,
            risk_amount=100.0,
            risk_percent=1.0,
            signal_score=80.0,
        )

        res = self.evaluate_paper_position_management(dummy_pos, current_price, current_atr, spec)
        if not res.success or res.action == "NO_ACTION" or res.new_sl == current_sl:
            return res

        # Submit modification request to MT5 terminal
        mt5 = self.demo_execution_engine.mt5_connection.get_mt5_module()
        if mt5 is None or self.demo_execution_engine.mt5_connection.state != ConnectionState.CONNECTED:
            return PositionModificationResult(
                success=False, action="MODIFICATION_FAILED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=res.new_sl, reason="REJECTED: MT5 terminal disconnected.", timestamp=now
            )

        request = {
            "action": getattr(mt5, "TRADE_ACTION_SLTP", 2),
            "position": ticket,
            "symbol": symbol,
            "sl": res.new_sl,
            "tp": current_tp,
        }

        logger.info(f"Submitting MT5 Position Modification Ticket #{ticket}: {res.action}, New SL={res.new_sl:.5f}")

        mod_result = mt5.order_send(request)
        if mod_result is None:
            return PositionModificationResult(
                success=False, action="MODIFICATION_FAILED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=res.new_sl, reason="REJECTED: MT5 order_send returned None.", timestamp=now
            )

        retcode = getattr(mod_result, "retcode", -1)
        done_retcode = getattr(mt5, "TRADE_RETCODE_DONE", 10009)

        if retcode == done_retcode:
            self.breakeven_applied_tickets.add(str(ticket))
            logger.info(f"MT5 Position Ticket #{ticket} Modified Successfully: New SL={res.new_sl:.5f}")
            return PositionModificationResult(
                success=True, action=res.action, ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=res.new_sl, old_tp=current_tp, new_tp=current_tp, reason=f"SUCCESS: MT5 position ticket #{ticket} updated.", timestamp=now
            )

        comment = getattr(mod_result, "comment", f"Retcode {retcode}")
        logger.error(f"MT5 Position Modification Failed: Ticket #{ticket}, Retcode={retcode}, Comment={comment}")
        return PositionModificationResult(
            success=False, action="MODIFICATION_FAILED", ticket=ticket, symbol=symbol, direction=direction, old_sl=current_sl, new_sl=res.new_sl, old_tp=current_tp, new_tp=current_tp, reason=f"REJECTED: MT5 modification failed (Retcode {retcode}: {comment}).", timestamp=now
        )
