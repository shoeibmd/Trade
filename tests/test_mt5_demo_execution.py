from datetime import datetime
from unittest.mock import MagicMock
import pytest

from trading.models import SignalType
from trading.signal_engine import SignalResult
from trading.risk_manager import RiskDecision, RiskManager, SymbolSpecification
from trading.mt5_connection import MT5Connection, ConnectionState
from trading.mt5_demo_execution import (
    MT5DemoExecutionEngine,
    DemoOrderResult,
    ACCOUNT_TRADE_MODE_DEMO,
    ACCOUNT_TRADE_MODE_REAL,
    ACCOUNT_TRADE_MODE_CONTEST,
)


def create_mock_signal_result(signal=SignalType.BUY, symbol="EURUSD"):
    return SignalResult(
        symbol=symbol,
        timeframe="M5",
        timestamp=datetime.now(),
        signal=signal,
        signal_score=85.0,
        bullish_score=85.0 if signal == SignalType.BUY else 0.0,
        bearish_score=85.0 if signal == SignalType.SELL else 0.0,
        minimum_signal_score=70.0,
        reasons=["Test signal reason"],
    )


def create_mock_risk_decision(approved=True, direction=SignalType.BUY, lot_size=0.66, symbol="EURUSD"):
    return RiskDecision(
        approved=approved,
        reason="APPROVED: Sample risk decision" if approved else "REJECTED: Sample rejection",
        symbol=symbol,
        direction=direction if approved else None,
        entry_price=1.0850 if approved else 0.0,
        stop_loss=1.0835 if approved else 0.0,
        take_profit=1.08725 if approved else 0.0,
        stop_distance=0.0015 if approved else 0.0,
        risk_amount=100.0 if approved else 0.0,
        risk_percent=1.0 if approved else 0.0,
        calculated_lot_size=lot_size if approved else 0.0,
        risk_reward_ratio=1.5 if approved else 0.0,
        account_equity=10000.0,
        daily_loss_percent=0.0,
        consecutive_losses=0,
        open_positions=0,
    )


def create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO, connected=True):
    mock_conn = MagicMock(spec=MT5Connection)
    mock_conn.state = ConnectionState.CONNECTED if connected else ConnectionState.DISCONNECTED

    mock_mt5 = MagicMock()
    mock_conn.get_mt5_module.return_value = mock_mt5

    # Mock account info
    acc_info = MagicMock()
    acc_info.login = 12345678
    acc_info.trade_mode = trade_mode
    acc_info.balance = 10000.0
    acc_info.equity = 10000.0
    acc_info.currency = "USD"
    acc_info.server = "MetaQuotes-Demo"
    acc_info.company = "MetaQuotes Software Corp."
    mock_mt5.account_info.return_value = acc_info

    # Mock tick
    tick = MagicMock()
    tick.ask = 1.0852
    tick.bid = 1.0850
    mock_mt5.symbol_info_tick.return_value = tick

    # Mock order_send success
    send_res = MagicMock()
    send_res.retcode = 10009  # TRADE_RETCODE_DONE
    send_res.order = 998877
    send_res.deal = 998877
    mock_mt5.order_send.return_value = send_res
    mock_mt5.TRADE_RETCODE_DONE = 10009
    mock_mt5.positions_get.return_value = []

    return mock_conn, mock_mt5


def test_default_paper_mode_blocks_demo_order():
    engine = MT5DemoExecutionEngine(system_mode="PAPER")
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "SAFETY GATE 1 REJECTED" in res.reason


def test_demo_mode_with_flag_disabled_blocks_order():
    engine = MT5DemoExecutionEngine(system_mode="DEMO", demo_trading_enabled=False)
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "SAFETY GATE 2 REJECTED" in res.reason


def test_live_trading_enabled_flag_blocks_order():
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO", demo_trading_enabled=True, live_trading_enabled=True
    )
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "SAFETY GATE 3 REJECTED" in res.reason


def test_real_money_account_blocks_all_order_placement():
    mock_conn, _ = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_REAL)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "SAFETY BLOCK" in res.reason
    assert "REAL MONEY account" in res.reason


def test_unknown_account_type_blocks_order_placement():
    mock_conn, _ = create_mock_mt5_conn(trade_mode=99)  # Unknown mode
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "SAFETY GATE 4 REJECTED" in res.reason


def test_disconnected_terminal_blocks_order_placement():
    mock_conn, _ = create_mock_mt5_conn(connected=False)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )
    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert "MT5 connection is not connected" in res.reason


def test_verified_demo_account_permits_demo_order_path():
    mock_conn, mock_mt5 = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )
    sig = create_mock_signal_result(signal=SignalType.BUY)
    risk = create_mock_risk_decision(approved=True, direction=SignalType.BUY)

    res = engine.execute_demo_order(sig, risk)

    assert res.success is True
    assert res.ticket == 998877
    assert res.volume == 0.66
    assert mock_mt5.order_send.called is True


def test_invalid_signal_or_rejected_risk_blocks_order():
    mock_conn, _ = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    # HOLD signal
    sig_hold = create_mock_signal_result(signal=SignalType.HOLD)
    risk_appr = create_mock_risk_decision(approved=True)
    res1 = engine.execute_demo_order(sig_hold, risk_appr)
    assert res1.success is False

    # Rejected risk decision
    sig_buy = create_mock_signal_result(signal=SignalType.BUY)
    risk_rejp = create_mock_risk_decision(approved=False)
    res2 = engine.execute_demo_order(sig_buy, risk_rejp)
    assert res2.success is False


def test_invalid_volume_or_sl_tp_blocks_order():
    mock_conn, _ = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    # Invalid volume < min
    sig = create_mock_signal_result()
    risk_small = create_mock_risk_decision(lot_size=0.001)  # min volume is 0.01
    res = engine.execute_demo_order(sig, risk_small)
    assert res.success is False
    assert "SAFETY GATE 6 REJECTED" in res.reason


def test_duplicate_signal_execution_protection():
    mock_conn, _ = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    # First execution -> Success
    res1 = engine.execute_demo_order(sig, risk)
    assert res1.success is True

    # Duplicate execution -> Blocked
    res2 = engine.execute_demo_order(sig, risk)
    assert res2.success is False
    assert "SAFETY GATE 7 REJECTED" in res.reason
    assert "Duplicate signal execution blocked" in res.reason


def test_application_restart_position_reconciliation():
    mock_conn, mock_mt5 = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)

    mock_pos = MagicMock()
    mock_pos.ticket = 554433
    mock_pos.symbol = "EURUSD"
    mock_pos.volume = 0.50
    mock_pos.price_open = 1.0850
    mock_pos.sl = 1.0835
    mock_pos.tp = 1.08725
    mock_pos.profit = 25.0
    mock_mt5.positions_get.return_value = [mock_pos]

    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    reconciled = engine.reconcile_open_positions(symbol="EURUSD")
    assert len(reconciled) == 1
    assert reconciled[0]["ticket"] == 554433
    assert reconciled[0]["volume"] == 0.50
    assert 554433 in engine.executed_tickets


def test_order_rejection_and_retcode_handling():
    mock_conn, mock_mt5 = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)

    # Mock order_send failure
    fail_res = MagicMock()
    fail_res.retcode = 10013  # TRADE_RETCODE_INVALID
    fail_res.comment = "Invalid volume"
    mock_mt5.order_send.return_value = fail_res

    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    sig = create_mock_signal_result()
    risk = create_mock_risk_decision()

    res = engine.execute_demo_order(sig, risk)
    assert res.success is False
    assert res.retcode == 10013
    assert "MT5 order_send failed" in res.reason


def test_credentials_privacy_in_logs(caplog):
    mock_conn, _ = create_mock_mt5_conn(trade_mode=ACCOUNT_TRADE_MODE_DEMO)
    engine = MT5DemoExecutionEngine(
        system_mode="DEMO",
        demo_trading_enabled=True,
        live_trading_enabled=False,
        mt5_connection=mock_conn,
    )

    engine.verify_account()

    # Confirm no password or secret token is logged
    for record in caplog.records:
        msg = record.getMessage().lower()
        assert "password" not in msg
        assert "secret" not in msg
        assert "token" not in msg
