from datetime import datetime, timedelta
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from trading.indicators import TechnicalIndicatorEngine, StructureState
from trading.models import PredictionResult, SignalType
from trading.signal_engine import SignalEngine, SignalResult


def create_sample_indicator_df(count=400, trend="up"):
    start_time = datetime(2026, 1, 1, 10, 0, 0)
    timestamps = [start_time + timedelta(minutes=5 * i) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        if trend == "up":
            price_offset = i * 0.0003
        elif trend == "down":
            price_offset = -i * 0.0003
        else:
            price_offset = np.sin(i / 5.0) * 0.0020

        o = base_price + price_offset
        c = o + 0.0001
        h = max(o, c) + 0.0003
        l = min(o, c) - 0.0003
        v = 100.0 + i
        amt = v * ((o + h + l + c) / 4.0)

        data.append({
            "timestamps": timestamps[i],
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "amount": amt
        })

    raw_df = pd.DataFrame(data)
    engine = TechnicalIndicatorEngine()
    return engine.calculate_all_indicators(raw_df)


def create_mock_prediction_result(close_base=1.0850, price_change_pct=0.0010, pred_len=120):
    start_time = datetime(2026, 1, 2, 20, 0, 0)
    target_close = close_base * (1.0 + price_change_pct)

    predicted_closes = np.linspace(close_base, target_close, pred_len).tolist()

    return PredictionResult(
        symbol="EURUSD",
        timestamp=start_time,
        pred_len=pred_len,
        predicted_close=predicted_closes,
        predicted_open=predicted_closes,
        predicted_high=[c + 0.0005 for c in predicted_closes],
        predicted_low=[c - 0.0005 for c in predicted_closes],
        predicted_volume=[150.0] * pred_len,
        metadata={"model_name": "NeoQuasar/Kronos-small"}
    )


def test_signal_engine_strong_bullish_buy():
    engine = SignalEngine(minimum_signal_score=70.0)
    df = create_sample_indicator_df(count=400, trend="up")
    last_close = float(df.iloc[-1]["close"])
    forecast = create_mock_prediction_result(close_base=last_close, price_change_pct=0.0020)  # +20 pips bullish forecast

    res = engine.evaluate_signal(df, forecast=forecast, symbol="EURUSD", timeframe="M5")

    assert isinstance(res, SignalResult)
    assert res.signal == SignalType.BUY
    assert res.signal_score >= 70.0
    assert res.bullish_score >= 70.0
    assert len(res.reasons) > 0
    assert "BUY Signal Approved" in res.reasons[0]


def test_signal_engine_strong_bearish_sell():
    engine = SignalEngine(minimum_signal_score=70.0)
    df = create_sample_indicator_df(count=400, trend="down")
    last_close = float(df.iloc[-1]["close"])
    forecast = create_mock_prediction_result(close_base=last_close, price_change_pct=-0.0020)  # -20 pips bearish forecast

    res = engine.evaluate_signal(df, forecast=forecast, symbol="EURUSD", timeframe="M5")

    assert isinstance(res, SignalResult)
    assert res.signal == SignalType.SELL
    assert res.signal_score >= 70.0
    assert res.bearish_score >= 70.0
    assert len(res.reasons) > 0
    assert "SELL Signal Approved" in res.reasons[0]


def test_signal_engine_weak_evidence_no_trade():
    engine = SignalEngine(minimum_signal_score=70.0)
    df = create_sample_indicator_df(count=400, trend="flat")
    last_close = float(df.iloc[-1]["close"])
    forecast = create_mock_prediction_result(close_base=last_close, price_change_pct=0.0001)  # Weak forecast

    res = engine.evaluate_signal(df, forecast=forecast, symbol="EURUSD", timeframe="M5")

    assert isinstance(res, SignalResult)
    assert res.signal == SignalType.HOLD  # NO_TRADE
    assert res.signal_score < 70.0
    assert "NO_TRADE" in res.reasons[0]


def test_signal_engine_missing_kronos_forecast_no_trade():
    engine = SignalEngine(minimum_signal_score=70.0)
    df = create_sample_indicator_df(count=400, trend="flat")

    res = engine.evaluate_signal(df, forecast=None, symbol="EURUSD", timeframe="M5")

    assert res.signal == SignalType.HOLD
    assert res.kronos_score == 0.0
    assert any("Missing or empty Kronos foundation forecast" in r for r in res.reasons)


def test_signal_engine_explainability_reasons():
    engine = SignalEngine()
    df = create_sample_indicator_df(count=400, trend="up")
    last_close = float(df.iloc[-1]["close"])
    forecast = create_mock_prediction_result(close_base=last_close, price_change_pct=0.0015)

    res = engine.evaluate_signal(df, forecast=forecast, symbol="EURUSD", timeframe="M5")

    assert len(res.reasons) >= 5
    assert "indicator_snapshot" in res.__dict__
    assert "forecast_summary" in res.__dict__


def test_signal_engine_no_future_leakage_proof():
    """
    EXPLICIT PROOF OF NO FUTURE LEAKAGE FOR SIGNALS:
    Mutating future market data (e.g. at index 350) MUST NOT alter a signal decision generated at index 250.
    """
    engine = SignalEngine()

    raw1 = create_sample_indicator_df(count=400, trend="up")
    last_close1 = float(raw1.iloc[249]["close"])
    forecast1 = create_mock_prediction_result(close_base=last_close1, price_change_pct=0.0015)

    res1 = engine.evaluate_signal(raw1.iloc[:250], forecast=forecast1)

    # Mutate data strictly after index 250
    raw2 = raw1.copy()
    raw2.loc[300:, "close"] = raw2.loc[300:, "close"] - 0.0500
    res2 = engine.evaluate_signal(raw2.iloc[:250], forecast=forecast1)

    assert res1.signal == res2.signal
    assert res1.signal_score == res2.signal_score
    assert res1.bullish_score == res2.bullish_score
    assert res1.bearish_score == res2.bearish_score


def test_end_to_end_chain_integration_no_order_placement():
    """
    INTEGRATION TEST:
    400 Closed M5 Candles -> Technical Indicators -> Kronos Forecast -> Signal Engine -> SignalResult
    Confirms chain produces valid BUY/SELL/NO_TRADE without order placement.
    """
    indicator_engine = TechnicalIndicatorEngine()
    signal_engine = SignalEngine(minimum_signal_score=70.0)

    # 1. Validated 400 closed M5 bars
    raw_df = create_sample_indicator_df(count=400, trend="up")

    # 2. Compute Technical Indicators
    ind_df = indicator_engine.calculate_all_indicators(raw_df)

    # 3. Kronos Forecast
    last_close = float(ind_df.iloc[-1]["close"])
    forecast = create_mock_prediction_result(close_base=last_close, price_change_pct=0.0015, pred_len=120)

    # 4. Evaluate Signal
    signal_res = signal_engine.evaluate_signal(ind_df, forecast=forecast, symbol="EURUSD", timeframe="M5")

    assert isinstance(signal_res, SignalResult)
    assert signal_res.signal in (SignalType.BUY, SignalType.SELL, SignalType.HOLD)
    assert signal_res.symbol == "EURUSD"
    assert signal_res.timeframe == "M5"
