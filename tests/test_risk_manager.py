from datetime import datetime, timedelta
import pytest
import pandas as pd
import numpy as np

from trading.models import SignalType, PredictionResult
from trading.indicators import TechnicalIndicatorEngine
from trading.signal_engine import SignalEngine, SignalResult
from trading.risk_manager import (
    RiskManager,
    RiskDecision,
    AccountState,
    SymbolSpecification,
)


def create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010, symbol="EURUSD"):
    return SignalResult(
        symbol=symbol,
        timeframe="M5",
        timestamp=datetime.now(),
        signal=signal,
        signal_score=85.0,
        bullish_score=85.0 if signal == SignalType.BUY else 0.0,
        bearish_score=85.0 if signal == SignalType.SELL else 0.0,
        minimum_signal_score=70.0,
        indicator_snapshot={"close": close, "atr_14": atr},
        forecast_summary={"price_change_pct": 0.0015},
    )


def test_risk_manager_initialization_defaults():
    rm = RiskManager()
    assert rm.risk_per_trade_percent == 1.0
    assert rm.max_open_positions == 1
    assert rm.max_daily_loss_percent == 3.0
    assert rm.max_consecutive_losses == 3
    assert rm.reward_risk_ratio == 1.5


def test_dynamic_lot_sizing_calculation():
    rm = RiskManager(risk_per_trade_percent=1.0)
    spec = SymbolSpecification()  # standard EURUSD 100k contract, tick_size=0.00001, tick_value=1.0
    sig = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)
    acc = AccountState(equity=10000.0, balance=10000.0, start_of_day_equity=10000.0)

    res = rm.evaluate_risk(sig, acc, spec)

    assert res.approved is True
    assert res.account_equity == 10000.0
    assert res.risk_amount == 100.0  # 1% of $10,000
    # Stop distance is ATR(0.0010) * 1.5 = 0.00150 (150 pips/points)
    # Loss per lot = 150 points * $1.0 = $150.0 per lot
    # Expected Lot = $100 / $150 = 0.6666... -> rounded down to 0.66 lots
    assert res.calculated_lot_size == 0.66
    assert res.stop_loss == 1.08350
    assert res.take_profit == 1.08725
    assert res.risk_reward_ratio == 1.5


def test_dynamic_lot_sizing_different_equities():
    rm = RiskManager(risk_per_trade_percent=1.0)
    spec = SymbolSpecification()
    sig = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)

    res_5k = rm.evaluate_risk(sig, AccountState(equity=5000.0), spec)
    res_50k = rm.evaluate_risk(sig, AccountState(equity=50000.0), spec)

    assert res_5k.risk_amount == 50.0
    assert res_5k.calculated_lot_size == 0.33
    assert res_50k.risk_amount == 500.0
    assert res_50k.calculated_lot_size == 3.33


def test_broker_lot_constraints_min_max_step():
    rm = RiskManager(risk_per_trade_percent=1.0)
    sig = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)

    # Small equity resulting in lot < min_lot
    spec_min = SymbolSpecification(volume_min=0.10)
    res_small = rm.evaluate_risk(sig, AccountState(equity=500.0), spec_min)
    assert res_small.approved is False
    assert "below broker minimum" in res_small.reason

    # Large equity resulting in max lot capping
    spec_max = SymbolSpecification(volume_max=2.0)
    res_large = rm.evaluate_risk(sig, AccountState(equity=100000.0), spec_max)
    assert res_large.approved is True
    assert res_large.calculated_lot_size == 2.0


def test_stop_loss_and_take_profit_buy_and_sell():
    rm = RiskManager(reward_risk_ratio=1.5)
    spec = SymbolSpecification()
    acc = AccountState(equity=10000.0)

    # BUY
    sig_buy = create_sample_signal_result(signal=SignalType.BUY, close=1.1000, atr=0.0020)
    res_buy = rm.evaluate_risk(sig_buy, acc, spec)
    assert res_buy.approved is True
    # SL distance = 0.0020 * 1.5 = 0.0030
    assert res_buy.stop_loss == 1.09700
    assert res_buy.take_profit == 1.10450

    # SELL
    sig_sell = create_sample_signal_result(signal=SignalType.SELL, close=1.1000, atr=0.0020)
    res_sell = rm.evaluate_risk(sig_sell, acc, spec)
    assert res_sell.approved is True
    assert res_sell.stop_loss == 1.10300
    assert res_sell.take_profit == 1.09550


def test_no_trade_signal_rejection():
    rm = RiskManager()
    spec = SymbolSpecification()
    acc = AccountState(equity=10000.0)
    sig_hold = create_sample_signal_result(signal=SignalType.HOLD)

    res = rm.evaluate_risk(sig_hold, acc, spec)
    assert res.approved is False
    assert "REJECTED: Signal is NO_TRADE / HOLD" in res.reason


def test_max_open_positions_rejection():
    rm = RiskManager(max_open_positions=1)
    spec = SymbolSpecification()
    sig = create_sample_signal_result(signal=SignalType.BUY)

    acc_busy = AccountState(equity=10000.0, open_positions_count=1)
    res = rm.evaluate_risk(sig, acc_busy, spec)

    assert res.approved is False
    assert "Maximum open positions limit reached" in res.reason


def test_daily_loss_limit_rejection():
    rm = RiskManager(max_daily_loss_percent=3.0)
    spec = SymbolSpecification()
    sig = create_sample_signal_result(signal=SignalType.BUY)

    # Equity dropped from $10,000 to $9,650 (3.5% daily loss)
    acc_loss = AccountState(equity=9650.0, start_of_day_equity=10000.0)
    res = rm.evaluate_risk(sig, acc_loss, spec)

    assert res.approved is False
    assert res.daily_loss_percent == 3.5
    assert "Maximum daily loss limit reached" in res.reason


def test_consecutive_loss_limit_rejection():
    rm = RiskManager(max_consecutive_losses=3)
    spec = SymbolSpecification()
    sig = create_sample_signal_result(signal=SignalType.BUY)

    acc_streaking = AccountState(equity=10000.0, consecutive_losses=3)
    res = rm.evaluate_risk(sig, acc_streaking, spec)

    assert res.approved is False
    assert "Maximum consecutive loss limit reached" in res.reason


def test_missing_atr_or_invalid_price_rejection():
    rm = RiskManager()
    spec = SymbolSpecification()
    acc = AccountState(equity=10000.0)

    # Missing ATR
    sig_no_atr = SignalResult(
        symbol="EURUSD",
        timeframe="M5",
        timestamp=datetime.now(),
        signal=SignalType.BUY,
        signal_score=80.0,
        bullish_score=80.0,
        bearish_score=0.0,
        minimum_signal_score=70.0,
        indicator_snapshot={"close": 1.0850, "atr_14": None},
    )
    res = rm.evaluate_risk(sig_no_atr, acc, spec)
    assert res.approved is False
    assert "Missing or invalid ATR" in res.reason


def test_risk_manager_determinism():
    rm = RiskManager()
    spec = SymbolSpecification()
    sig = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)
    acc = AccountState(equity=10000.0)

    res1 = rm.evaluate_risk(sig, acc, spec)
    res2 = rm.evaluate_risk(sig, acc, spec)

    assert res1.approved == res2.approved
    assert res1.calculated_lot_size == res2.calculated_lot_size
    assert res1.stop_loss == res2.stop_loss
    assert res1.take_profit == res2.take_profit


def test_lot_rounding_safety_never_exceeds_max_risk():
    """
    SAFETY TEST:
    Verifies that lot size rounding TRUNCATES DOWNWARD and NEVER rounds upward
    in a way that causes actual monetary risk to exceed the configured risk percentage.
    """
    rm = RiskManager(risk_per_trade_percent=1.0)
    spec = SymbolSpecification()  # 100k contract, tick_size=0.00001, tick_value=1.0
    sig = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)
    acc = AccountState(equity=10000.0)  # Max risk = $100.00

    res = rm.evaluate_risk(sig, acc, spec)

    assert res.approved is True
    # Stop distance = 0.00150 -> Monetary loss per lot = $150.00
    # Raw lot size = $100 / $150 = 0.666666...
    # Downward truncated lot size = 0.66
    assert res.calculated_lot_size == 0.66

    # Actual monetary loss at SL
    actual_monetary_loss = res.calculated_lot_size * 150.0  # 0.66 * $150 = $99.00
    actual_risk_percent = (actual_monetary_loss / acc.equity) * 100.0

    assert actual_monetary_loss <= res.risk_amount  # $99.00 <= $100.00
    assert actual_risk_percent <= rm.risk_per_trade_percent  # 0.99% <= 1.0%


def test_end_to_end_chain_signal_to_risk_decision():
    """
    End-to-end chain integration:
    SignalResult -> RiskManager -> RiskDecision
    Confirms chain produces approved decision for valid BUY and rejected decision for NO_TRADE.
    """
    rm = RiskManager(risk_per_trade_percent=1.0, reward_risk_ratio=1.5)
    spec = SymbolSpecification()
    acc = AccountState(equity=10000.0)

    # 1. Valid BUY Signal -> Approved Risk Decision
    sig_buy = create_sample_signal_result(signal=SignalType.BUY, close=1.0850, atr=0.0010)
    dec_buy = rm.evaluate_risk(sig_buy, acc, spec)

    assert isinstance(dec_buy, RiskDecision)
    assert dec_buy.approved is True
    assert dec_buy.direction == SignalType.BUY
    assert dec_buy.calculated_lot_size > 0
    assert dec_buy.stop_loss < dec_buy.entry_price < dec_buy.take_profit

    # 2. NO_TRADE Signal -> Rejected Risk Decision
    sig_hold = create_sample_signal_result(signal=SignalType.HOLD)
    dec_hold = rm.evaluate_risk(sig_hold, acc, spec)

    assert isinstance(dec_hold, RiskDecision)
    assert dec_hold.approved is False
    assert dec_hold.direction is None
    assert dec_hold.calculated_lot_size == 0.0
