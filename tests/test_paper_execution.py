from datetime import datetime, timedelta
import os
import sqlite3
import pytest
import pandas as pd
import numpy as np

from trading.models import SignalType, PredictionResult
from trading.indicators import TechnicalIndicatorEngine
from trading.signal_engine import SignalEngine, SignalResult
from trading.risk_manager import RiskManager, RiskDecision, AccountState, SymbolSpecification
from trading.paper_execution import (
    PaperExecutionEngine,
    PaperPosition,
    PaperTradeRecord,
    PaperAccountState,
)


def create_sample_risk_decision(
    approved=True,
    direction=SignalType.BUY,
    entry_price=1.0850,
    stop_loss=1.0835,
    take_profit=1.08725,
    lot_size=0.66,
    symbol="EURUSD",
):
    return RiskDecision(
        approved=approved,
        reason="APPROVED: Sample test decision" if approved else "REJECTED: Sample test rejection",
        symbol=symbol,
        direction=direction if approved else None,
        entry_price=entry_price if approved else 0.0,
        stop_loss=stop_loss if approved else 0.0,
        take_profit=take_profit if approved else 0.0,
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


def create_sample_signal_result(signal=SignalType.BUY, close=1.0850, symbol="EURUSD"):
    return SignalResult(
        symbol=symbol,
        timeframe="M5",
        timestamp=datetime.now(),
        signal=signal,
        signal_score=85.0,
        bullish_score=85.0 if signal == SignalType.BUY else 0.0,
        bearish_score=85.0 if signal == SignalType.SELL else 0.0,
        minimum_signal_score=70.0,
        indicator_snapshot={"close": close, "atr_14": 0.0010},
        reasons=["Test signal reason"],
    )


def test_paper_engine_initialization_defaults(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file, initial_balance=10000.0)
    assert engine.account_state.balance == 10000.0
    assert engine.account_state.equity == 10000.0
    assert engine.account_state.open_position is None
    assert os.path.exists(db_file)


def test_approved_buy_and_sell_position_creation(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    # BUY position
    dec_buy = create_sample_risk_decision(approved=True, direction=SignalType.BUY)
    sig_buy = create_sample_signal_result(signal=SignalType.BUY)
    pos_buy = engine.execute_risk_decision(dec_buy, sig_buy, spec)

    assert isinstance(pos_buy, PaperPosition)
    assert pos_buy.direction == SignalType.BUY
    assert pos_buy.entry_price == 1.0850
    assert pos_buy.lot_size == 0.66
    assert engine.account_state.open_position == pos_buy

    # Try opening second position when one is open -> Rejected
    dec_buy2 = create_sample_risk_decision(approved=True, direction=SignalType.BUY)
    pos_buy2 = engine.execute_risk_decision(dec_buy2, sig_buy, spec)
    assert pos_buy2 is None


def test_no_trade_and_rejected_risk_decision_creates_no_position(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    dec_rejected = create_sample_risk_decision(approved=False)
    sig_hold = create_sample_signal_result(signal=SignalType.HOLD)

    pos = engine.execute_risk_decision(dec_rejected, sig_hold, spec)
    assert pos is None
    assert engine.account_state.open_position is None


def test_sl_and_tp_hit_position_closing(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    # 1. Take Profit Hit on BUY
    dec_tp = create_sample_risk_decision(approved=True, direction=SignalType.BUY, entry_price=1.0850, stop_loss=1.0835, take_profit=1.08725, lot_size=1.0)
    sig_tp = create_sample_signal_result(signal=SignalType.BUY)
    engine.execute_risk_decision(dec_tp, sig_tp, spec)

    bars_tp = pd.DataFrame([{
        "timestamps": datetime.now() + timedelta(minutes=5),
        "open": 1.0855, "high": 1.0875, "low": 1.0850, "close": 1.0873, "volume": 100.0
    }])

    record_tp = engine.process_subsequent_bars(bars_tp, spec)
    assert isinstance(record_tp, PaperTradeRecord)
    assert record_tp.exit_reason == "TAKE_PROFIT"
    assert record_tp.profit_loss == 225.0  # (1.08725 - 1.0850) / 0.00001 * 1.0 * 1.0 = $225.00
    assert engine.account_state.balance == 10225.0
    assert engine.account_state.open_position is None

    # 2. Stop Loss Hit on SELL
    dec_sl = create_sample_risk_decision(approved=True, direction=SignalType.SELL, entry_price=1.0850, stop_loss=1.0865, take_profit=1.08275, lot_size=1.0)
    sig_sl = create_sample_signal_result(signal=SignalType.SELL)
    engine.execute_risk_decision(dec_sl, sig_sl, spec)

    bars_sl = pd.DataFrame([{
        "timestamps": datetime.now() + timedelta(minutes=10),
        "open": 1.0855, "high": 1.0870, "low": 1.0840, "close": 1.0868, "volume": 100.0
    }])

    record_sl = engine.process_subsequent_bars(bars_sl, spec)
    assert isinstance(record_sl, PaperTradeRecord)
    assert record_sl.exit_reason == "STOP_LOSS"
    assert record_sl.profit_loss == -150.0  # (1.0850 - 1.0865) / 0.00001 * 1.0 * 1.0 = -$150.00
    assert engine.account_state.balance == 10075.0  # $10225 - $150 = $10075


def test_same_candle_sl_tp_ambiguity_conservative_sl_rule(tmp_path):
    """
    AMBIGUITY TEST:
    If a candle's range touches both SL and TP, the engine MUST deterministically
    prioritize SL over TP (pessimistic conservative rule).
    """
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    dec = create_sample_risk_decision(approved=True, direction=SignalType.BUY, entry_price=1.0850, stop_loss=1.0835, take_profit=1.08725, lot_size=1.0)
    sig = create_sample_signal_result(signal=SignalType.BUY)
    engine.execute_risk_decision(dec, sig, spec)

    # Spike bar touching BOTH SL (low 1.0830 <= 1.0835) AND TP (high 1.0880 >= 1.08725)
    spike_bar = pd.DataFrame([{
        "timestamps": datetime.now() + timedelta(minutes=5),
        "open": 1.0850, "high": 1.0880, "low": 1.0830, "close": 1.0840, "volume": 500.0
    }])

    record = engine.process_subsequent_bars(spike_bar, spec)
    assert record is not None
    assert "STOP_LOSS" in record.exit_reason
    assert "Same-candle ambiguity" in record.exit_reason
    assert record.exit_price == 1.0835
    assert record.profit_loss == -150.0


def test_pnl_calculation_formulas():
    spec = SymbolSpecification(tick_size=0.00001, tick_value=1.0)

    # BUY Profit
    pnl_buy_prof = PaperExecutionEngine.calculate_pnl(SignalType.BUY, 1.0850, 1.0870, 1.0, spec)
    assert pnl_buy_prof == 200.0

    # BUY Loss
    pnl_buy_loss = PaperExecutionEngine.calculate_pnl(SignalType.BUY, 1.0850, 1.0830, 1.0, spec)
    assert pnl_buy_loss == -200.0

    # SELL Profit
    pnl_sell_prof = PaperExecutionEngine.calculate_pnl(SignalType.SELL, 1.0850, 1.0830, 1.0, spec)
    assert pnl_sell_prof == 200.0

    # SELL Loss
    pnl_sell_loss = PaperExecutionEngine.calculate_pnl(SignalType.SELL, 1.0850, 1.0870, 1.0, spec)
    assert pnl_sell_loss == -200.0


def test_account_state_updates_and_risk_manager_feedback(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file, initial_balance=10000.0)
    spec = SymbolSpecification()

    # Execute winning trade
    dec1 = create_sample_risk_decision(approved=True, direction=SignalType.BUY, entry_price=1.0850, stop_loss=1.0835, take_profit=1.08725, lot_size=1.0)
    sig1 = create_sample_signal_result(signal=SignalType.BUY)
    engine.execute_risk_decision(dec1, sig1, spec)

    bars_win = pd.DataFrame([{"timestamps": datetime.now(), "open": 1.0850, "high": 1.0875, "low": 1.0850, "close": 1.0875}])
    engine.process_subsequent_bars(bars_win, spec)

    summary = engine.get_performance_summary()
    assert summary["total_trades"] == 1
    assert summary["winning_trades"] == 1
    assert summary["net_pnl"] == 225.0
    assert summary["win_rate_pct"] == 100.0

    # Verify RiskManager AccountState conversion
    risk_acc = engine.get_risk_account_state()
    assert isinstance(risk_acc, AccountState)
    assert risk_acc.equity == 10225.0
    assert risk_acc.open_positions_count == 0


def test_sqlite_trade_persistence(tmp_path):
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    dec = create_sample_risk_decision(approved=True, direction=SignalType.BUY, entry_price=1.0850, stop_loss=1.0835, take_profit=1.08725, lot_size=1.0)
    sig = create_sample_signal_result(signal=SignalType.BUY)
    engine.execute_risk_decision(dec, sig, spec)

    bars = pd.DataFrame([{"timestamps": datetime.now(), "open": 1.0850, "high": 1.0875, "low": 1.0850, "close": 1.0875}])
    trade_rec = engine.process_subsequent_bars(bars, spec)

    # Verify persistence in SQLite table
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id, symbol, direction, profit_loss FROM paper_trades WHERE trade_id = ?", (trade_rec.trade_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == trade_rec.trade_id
        assert row[1] == "EURUSD"
        assert row[2] == "BUY"
        assert row[3] == 225.0


def test_no_future_leakage_in_paper_engine(tmp_path):
    """
    PROOF OF NO FUTURE LEAKAGE:
    Entry price and position state are formed strictly at the decision timestamp.
    Subsequent future candle changes cannot retroactively modify entry price or SL/TP targets.
    """
    db_file = str(tmp_path / "test_paper.db")
    engine = PaperExecutionEngine(db_path=db_file)
    spec = SymbolSpecification()

    entry_time = datetime(2026, 1, 1, 12, 0, 0)
    dec = create_sample_risk_decision(approved=True, direction=SignalType.BUY, entry_price=1.0850, stop_loss=1.0835, take_profit=1.08725, lot_size=1.0)
    dec.timestamp = entry_time
    sig = create_sample_signal_result(signal=SignalType.BUY)

    pos = engine.execute_risk_decision(dec, sig, spec)
    original_entry = pos.entry_price
    original_sl = pos.stop_loss
    original_tp = pos.take_profit

    # Process wild future bars that do not hit SL/TP
    wild_bars = pd.DataFrame([
        {"timestamps": entry_time + timedelta(minutes=5), "open": 1.0850, "high": 1.0865, "low": 1.0840, "close": 1.0860},
        {"timestamps": entry_time + timedelta(minutes=10), "open": 1.0860, "high": 1.0868, "low": 1.0845, "close": 1.0855},
    ])
    engine.process_subsequent_bars(wild_bars, spec)

    # Verify open position state remains completely uncorrupted
    pos_current = engine.account_state.open_position
    assert pos_current.entry_price == original_entry == 1.0850
    assert pos_current.stop_loss == original_sl == 1.0835
    assert pos_current.take_profit == original_tp == 1.08725


def test_end_to_end_full_trading_chain(tmp_path):
    """
    FULL END-TO-END CHAIN INTEGRATION:
    400 Closed M5 Candles -> Technical Indicators -> Kronos Forecast -> Signal Engine -> Risk Manager -> Paper Trading Engine -> Simulated Candles -> Trade Close
    """
    db_file = str(tmp_path / "test_paper_e2e.db")
    indicator_engine = TechnicalIndicatorEngine()
    signal_engine = SignalEngine(minimum_signal_score=70.0)
    risk_manager = RiskManager(risk_per_trade_percent=1.0, reward_risk_ratio=1.5)
    paper_engine = PaperExecutionEngine(db_path=db_file, initial_balance=10000.0)
    spec = SymbolSpecification()

    # 1. 400 closed M5 bars
    timestamps = [datetime(2026, 1, 1, 10, 0) + timedelta(minutes=5 * i) for i in range(400)]
    raw_data = []
    base_p = 1.0850
    for i in range(400):
        o = base_p + i * 0.0003
        c = o + 0.0001
        raw_data.append({"timestamps": timestamps[i], "open": o, "high": max(o, c) + 0.0003, "low": min(o, c) - 0.0003, "close": c, "volume": 100.0 + i, "amount": 100.0 * c})
    raw_df = pd.DataFrame(raw_data)

    # 2. Indicators
    ind_df = indicator_engine.calculate_all_indicators(raw_df)
    last_close = float(ind_df.iloc[-1]["close"])

    # 3. Forecast
    pred_closes = np.linspace(last_close, last_close + 0.0030, 120).tolist()
    forecast = PredictionResult(symbol="EURUSD", timestamp=datetime.now(), pred_len=120, predicted_close=pred_closes, predicted_open=pred_closes, predicted_high=[c + 0.0005 for c in pred_closes], predicted_low=[c - 0.0005 for c in pred_closes], predicted_volume=[150.0] * 120)

    # 4. Signal
    sig_res = signal_engine.evaluate_signal(ind_df, forecast=forecast)
    assert sig_res.signal == SignalType.BUY

    # 5. Risk Decision
    risk_acc = paper_engine.get_risk_account_state()
    risk_dec = risk_manager.evaluate_risk(sig_res, risk_acc, spec, indicator_df=ind_df)
    assert risk_dec.approved is True

    # 6. Paper Execution
    paper_pos = paper_engine.execute_risk_decision(risk_dec, sig_res, spec)
    assert paper_pos is not None
    assert paper_engine.account_state.open_position == paper_pos

    # 7. Simulated subsequent candle triggering Take Profit
    future_bars = pd.DataFrame([{
        "timestamps": datetime.now() + timedelta(minutes=5),
        "open": risk_dec.entry_price,
        "high": risk_dec.take_profit + 0.0010,
        "low": risk_dec.entry_price - 0.0001,
        "close": risk_dec.take_profit,
        "volume": 200.0
    }])

    closed_trade = paper_engine.process_subsequent_bars(future_bars, spec)
    assert closed_trade is not None
    assert closed_trade.exit_reason == "TAKE_PROFIT"
    assert closed_trade.profit_loss > 0
    assert paper_engine.account_state.balance > 10000.0
    assert paper_engine.account_state.open_position is None
