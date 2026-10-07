from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest

from trading.indicators import StructureState, TechnicalIndicatorEngine


def create_sample_ohlc_df(count=400, start_time=None, timeframe_min=5, trend="up"):
    if start_time is None:
        start_time = datetime(2026, 1, 1, 10, 0, 0)

    timestamps = [start_time + timedelta(minutes=i * timeframe_min) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        if trend == "up":
            price_offset = i * 0.0002
        elif trend == "down":
            price_offset = -i * 0.0002
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

    return pd.DataFrame(data)


def test_ema_calculation_and_warmup():
    engine = TechnicalIndicatorEngine(ema_fast=9)
    df = create_sample_ohlc_df(count=100)

    ema9 = engine.compute_ema(df["close"], period=9)

    # First 8 rows must be NaN due to warm-up
    assert ema9.iloc[:8].isnull().all()
    # Row 9 onwards must be valid numeric
    assert not ema9.iloc[8:].isnull().any()
    assert len(ema9) == 100


def test_rsi_calculation_and_bounds():
    engine = TechnicalIndicatorEngine(rsi_period=14)
    df = create_sample_ohlc_df(count=100, trend="up")

    rsi14 = engine.compute_rsi(df["close"], period=14)

    # First 14 rows must be NaN
    assert rsi14.iloc[:14].isnull().all()
    # Strong uptrend should yield high RSI (> 70)
    assert rsi14.iloc[-1] > 70.0
    assert (rsi14.dropna() >= 0.0).all() and (rsi14.dropna() <= 100.0).all()


def test_atr_calculation():
    engine = TechnicalIndicatorEngine(atr_period=14)
    df = create_sample_ohlc_df(count=100)

    atr14 = engine.compute_atr(df["high"], df["low"], df["close"], period=14)

    assert atr14.iloc[:14].isnull().all()
    assert (atr14.dropna() > 0.0).all()


def test_adx_calculation():
    engine = TechnicalIndicatorEngine(adx_period=14)
    df = create_sample_ohlc_df(count=100, trend="up")

    adx, plus_di, minus_di = engine.compute_adx(df["high"], df["low"], df["close"], period=14)

    # In a strong uptrend, +DI must exceed -DI
    valid_idx = 30
    assert plus_di.iloc[valid_idx] > minus_di.iloc[valid_idx]
    assert not np.isnan(adx.iloc[-1])


def test_market_structure_identification():
    engine = TechnicalIndicatorEngine(swing_window=5)
    df = create_sample_ohlc_df(count=100, trend="wave")

    struct = engine.compute_market_structure(df)

    assert isinstance(struct.state, StructureState)
    assert struct.recent_swing_high is not None
    assert struct.recent_swing_low is not None


def test_no_future_leakage_proof():
    """
    CRITICAL PROOF OF NO FUTURE LEAKAGE:
    Modifying future candles (e.g. index 350) MUST NOT alter indicator values calculated at earlier candles (e.g. index 200).
    """
    engine = TechnicalIndicatorEngine()

    df1 = create_sample_ohlc_df(count=400, trend="wave")
    out1 = engine.calculate_all_indicators(df1)

    # Create df2 by altering price values strictly AFTER index 250
    df2 = df1.copy()
    df2.loc[300:, "close"] = df2.loc[300:, "close"] + 0.0500
    df2.loc[300:, "high"] = df2.loc[300:, "high"] + 0.0500
    out2 = engine.calculate_all_indicators(df2)

    # Verify that indicators up to index 250 are 100% IDENTICAL
    check_cols = ["ema_9", "ema_21", "rsi_14", "atr_14", "adx_14", "plus_di_14", "minus_di_14"]
    for col in check_cols:
        pd.testing.assert_series_equal(
            out1.loc[:250, col],
            out2.loc[:250, col],
            check_exact=True,
            check_names=True,
            obj=f"Future leakage detected in column {col}"
        )


def test_insufficient_history_handling():
    engine = TechnicalIndicatorEngine()
    df_tiny = create_sample_bars_df_short(count=5)

    # Should not crash, returns NaNs for warm-up indicators
    ema = engine.compute_ema(df_tiny["close"], 20)
    assert ema.isnull().all()


def test_calculate_all_indicators_integration_400_closed_bars():
    engine = TechnicalIndicatorEngine()
    df = create_sample_ohlc_df(count=400)

    out_df = engine.calculate_all_indicators(df)

    assert len(out_df) == 400
    expected_cols = [
        "timestamps", "open", "high", "low", "close", "volume", "amount",
        "ema_9", "ema_21", "ema_50", "ema_200", "rsi_14", "atr_14",
        "adx_14", "plus_di_14", "minus_di_14", "market_structure_state"
    ]
    for col in expected_cols:
        assert col in out_df.columns

    # Verify tail values are non-NaN
    assert not out_df[["ema_9", "ema_21", "rsi_14", "atr_14"]].iloc[-1].isnull().any()


def create_sample_bars_df_short(count=5):
    timestamps = [datetime(2026, 1, 1, 10, 0) + timedelta(minutes=5 * i) for i in range(count)]
    return pd.DataFrame({
        "timestamps": timestamps,
        "open": np.full(count, 1.0850),
        "high": np.full(count, 1.0860),
        "low": np.full(count, 1.0840),
        "close": np.full(count, 1.0855),
        "volume": np.full(count, 100.0),
        "amount": np.full(count, 108.55)
    })
