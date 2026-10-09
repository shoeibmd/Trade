from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest

from trading.models import SignalType
from trading.risk_manager import SymbolSpecification
from trading.paper_execution import PaperPosition
from trading.mt5_connection import MT5Connection, ConnectionState
from trading.mt5_demo_execution import MT5DemoExecutionEngine, ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL
from trading.position_manager import PositionManager, PositionModificationResult


def create_sample_paper_pos(
    direction=SignalType.BUY, entry=1.0850, sl=1.0835, tp=1.08725, pos_id="pos_123"
):
    return PaperPosition(
        position_id=pos_id,
        symbol="EURUSD",
        timeframe="M5",
        direction=direction,
        entry_timestamp=datetime.now(),
        entry_price=entry,
        lot_size=0.5,
        stop_loss=sl,
        take_profit=tp,
        risk_amount=100.0,
        risk_percent=1.0,
        signal_score=80.0,
    )


def create_mock_demo_engine(trade_mode=ACCOUNT_TRADE_MODE_DEMO, connected=True):
    mock_conn = MagicMock(spec=MT5Connection)
    mock_conn.state = ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED

    mock_mt5 = MagicMock()
    mock_conn.get_mt5_module.return_value = mock_mt5

    acc_info = MagicMock()
    acc_info.login = 12345678
    acc_info.trade_mode = trade_mode
    acc_info.server = "MetaQuotes-Demo"
    acc_info.company = "MetaQuotes Software Corp."
    mock_mt5.account_info.return_value = acc_info

    mod_res = MagicMock()
    mod_res.retcode = 10009  # TRADE_RETCODE_DONE
    mock_mt5.order_send.return_value = mod_res
    mock_mt5.TRADE_RETCODE_DONE = 10009

    demo_engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )
    return demo_engine, mock_mt5


def test_position_manager_initialization_defaults():
    pm = PositionManager()
    assert pm.breakeven_r_multiple == 1.0
    assert pm.breakeven_offset_points == 10
    assert pm.trailing_stop_atr_multiplier == 1.5
    assert pm.trailing_stop_activation_r_multiple == 1.2
    assert pm.polling_interval_seconds == 5


def test_buy_position_breakeven_activation():
    pm = PositionManager(breakeven_r_multiple=1.0, breakeven_offset_points=10)
    spec = SymbolSpecification(point=0.00001, digits=5)
    # Entry: 1.0850, SL: 1.0835 (stop_dist = 0.0015)
    # 1.0R profit = +0.0015 -> price = 1.0865
    pos = create_sample_paper_pos(direction=SignalType.BUY, entry=1.0850, sl=1.0835)

    res = pm.evaluate_paper_position_management(
        paper_pos=pos, current_price=1.0866, current_atr=0.0010, symbol_spec=spec
    )

    assert res.success is True
    assert res.action == "BREAKEVEN_APPLIED"
    # Target SL = entry + 10 points = 1.0850 + 0.00010 = 1.08510
    assert res.new_sl == 1.08510
    assert pos.stop_loss == 1.08510


def test_sell_position_breakeven_activation():
    pm = PositionManager(breakeven_r_multiple=1.0, breakeven_offset_points=10)
    spec = SymbolSpecification(point=0.00001, digits=5)
    # Entry: 1.0850, SL: 1.0865 (stop_dist = 0.0015)
    # 1.0R profit = -0.0015 -> price = 1.0835
    pos = create_sample_paper_pos(direction=SignalType.SELL, entry=1.0850, sl=1.0865)

    res = pm.evaluate_paper_position_management(
        paper_pos=pos, current_price=1.0834, current_atr=0.0010, symbol_spec=spec
    )

    assert res.success is True
    assert res.action == "BREAKEVEN_APPLIED"
    # Target SL = entry - 10 points = 1.0850 - 0.00010 = 1.08490
    assert res.new_sl == 1.08490
    assert pos.stop_loss == 1.08490


def test_buy_position_atr_trailing_stop_activation():
    pm = PositionManager(trailing_stop_activation_r_multiple=1.2, trailing_stop_atr_multiplier=1.5)
    spec = SymbolSpecification(point=0.00001, digits=5)
    pos = create_sample_paper_pos(direction=SignalType.BUY, entry=1.0850, sl=1.0835)  # stop_dist=0.0015

    # Profit = 1.0880 - 1.0850 = +0.0030 (2.0R > 1.2R)
    # Trail SL = 1.0880 - (1.5 * 0.0010) = 1.0880 - 0.0015 = 1.08650
    res = pm.evaluate_paper_position_management(
        paper_pos=pos, current_price=1.0880, current_atr=0.0010, symbol_spec=spec
    )

    assert res.success is True
    assert res.action == "TRAILING_STOP_UPDATED"
    assert res.new_sl == 1.08650
    assert pos.stop_loss == 1.08650


def test_progressive_lifecycle_buy_and_sell_positions():
    """
    PROGRESSIVE LIFECYCLE TEST:
    Verifies that a BUY and SELL position progresses smoothly through:
    Initial SL -> Break-Even -> Multiple Trailing Stop updates.
    """
    pm = PositionManager(breakeven_r_multiple=1.0, trailing_stop_activation_r_multiple=1.2)
    spec = SymbolSpecification(point=0.00001, digits=5)

    # 1. BUY Progressive Lifecycle
    pos_buy = create_sample_paper_pos(direction=SignalType.BUY, entry=1.0850, sl=1.0835)  # stop_dist=0.0015
    # Step 1: Initial state
    assert pos_buy.stop_loss == 1.0835

    # Step 2: Price moves to 1.0866 (1.06R > 1.0R) -> Break-Even applied
    res1 = pm.evaluate_paper_position_management(pos_buy, 1.0866, 0.0010, spec)
    assert res1.action == "BREAKEVEN_APPLIED"
    assert pos_buy.stop_loss == 1.08510

    # Step 3: Price moves to 1.0880 (2.0R > 1.2R) -> Trailing Stop 1 applied
    res2 = pm.evaluate_paper_position_management(pos_buy, 1.0880, 0.0010, spec)
    assert res2.action == "TRAILING_STOP_UPDATED"
    assert pos_buy.stop_loss == 1.08650  # 1.0880 - 0.0015 = 1.08650

    # Step 4: Price moves higher to 1.0895 -> Trailing Stop 2 applied
    res3 = pm.evaluate_paper_position_management(pos_buy, 1.0895, 0.0010, spec)
    assert res3.action == "TRAILING_STOP_UPDATED"
    assert pos_buy.stop_loss == 1.08800  # 1.0895 - 0.0015 = 1.08800

    # 2. SELL Progressive Lifecycle
    pos_sell = create_sample_paper_pos(direction=SignalType.SELL, entry=1.0850, sl=1.0865)  # stop_dist=0.0015
    # Step 1: Initial state
    assert pos_sell.stop_loss == 1.0865

    # Step 2: Price moves down to 1.0834 (1.06R > 1.0R) -> Break-Even applied
    res_s1 = pm.evaluate_paper_position_management(pos_sell, 1.0834, 0.0010, spec)
    assert res_s1.action == "BREAKEVEN_APPLIED"
    assert pos_sell.stop_loss == 1.08490

    # Step 3: Price moves down to 1.0820 (2.0R > 1.2R) -> Trailing Stop 1 applied
    res_s2 = pm.evaluate_paper_position_management(pos_sell, 1.0820, 0.0010, spec)
    assert res_s2.action == "TRAILING_STOP_UPDATED"
    assert pos_sell.stop_loss == 1.08350  # 1.0820 + 0.0015 = 1.08350

    # Step 4: Price moves lower to 1.0805 -> Trailing Stop 2 applied
    res_s3 = pm.evaluate_paper_position_management(pos_sell, 1.0805, 0.0010, spec)
    assert res_s3.action == "TRAILING_STOP_UPDATED"
    assert pos_sell.stop_loss == 1.08200  # 1.0805 + 0.0015 = 1.08200


def test_strict_non_regression_rule_sl_never_moves_backward():
    """
    STRICT NON-REGRESSION RULE:
    SL must NEVER move backward or increase risk for either BUY or SELL positions.
    """
    pm = PositionManager()
    spec = SymbolSpecification(point=0.00001, digits=5)

    # 1. BUY: Current SL is 1.0860. Proposed SL < 1.0860 -> REJECTED
    pos_buy = create_sample_paper_pos(direction=SignalType.BUY, entry=1.0850, sl=1.0860)
    res_buy = pm.evaluate_paper_position_management(
        paper_pos=pos_buy, current_price=1.0855, current_atr=0.0010, symbol_spec=spec
    )
    assert res_buy.action in ("NO_ACTION", "REJECTED")
    assert pos_buy.stop_loss == 1.0860  # SL preserved

    # 2. SELL: Current SL is 1.0840. Proposed SL > 1.0840 -> REJECTED
    pos_sell = create_sample_paper_pos(direction=SignalType.SELL, entry=1.0850, sl=1.0840)
    res_sell = pm.evaluate_paper_position_management(
        paper_pos=pos_sell, current_price=1.0845, current_atr=0.0010, symbol_spec=spec
    )
    assert res_sell.action in ("NO_ACTION", "REJECTED")
    assert pos_sell.stop_loss == 1.0840  # SL preserved


def test_missing_or_invalid_position_handling():
    pm = PositionManager()
    res = pm.evaluate_paper_position_management(
        paper_pos=None, current_price=1.0850, current_atr=0.0010
    )
    assert res.success is False
    assert "REJECTED" in res.action


def test_idempotency_on_repeated_polling():
    pm = PositionManager()
    spec = SymbolSpecification(point=0.00001, digits=5)
    pos = create_sample_paper_pos(direction=SignalType.BUY, entry=1.0850, sl=1.0835)

    # First polling cycle: Applies break-even
    res1 = pm.evaluate_paper_position_management(pos, 1.0866, 0.0010, spec)
    assert res1.action == "BREAKEVEN_APPLIED"

    # Second polling cycle at same price: NO_ACTION (idempotent)
    res2 = pm.evaluate_paper_position_management(pos, 1.0866, 0.0010, spec)
    assert res2.action == "NO_ACTION"
    assert res2.new_sl == res1.new_sl


def test_demo_position_modification_guarded_by_safety_gates():
    demo_engine, mock_mt5 = create_mock_demo_engine(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    pm = PositionManager(demo_execution_engine=demo_engine)
    spec = SymbolSpecification(point=0.00001, digits=5)

    res = pm.evaluate_and_modify_demo_position(
        ticket=991122,
        symbol="EURUSD",
        direction=SignalType.BUY,
        entry_price=1.0850,
        current_sl=1.0835,
        current_tp=1.08725,
        current_price=1.0866,
        current_atr=0.0010,
        symbol_spec=spec,
    )

    assert res.success is True
    assert res.action == "BREAKEVEN_APPLIED"
    assert mock_mt5.order_send.called is True


def test_real_account_blocks_demo_position_modification():
    demo_engine, _ = create_mock_demo_engine(trade_mode=ACCOUNT_TRADE_MODE_REAL)
    pm = PositionManager(demo_execution_engine=demo_engine)

    res = pm.evaluate_and_modify_demo_position(
        ticket=991122,
        symbol="EURUSD",
        direction=SignalType.BUY,
        entry_price=1.0850,
        current_sl=1.0835,
        current_tp=1.08725,
        current_price=1.0866,
        current_atr=0.0010,
    )

    assert res.success is False
    assert "REJECTED" in res.action
    assert "Account verification failed" in res.reason
