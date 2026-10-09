from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np

from trading.models import SignalType, PredictionResult
from trading.kronos_adapter import KronosAdapter
from trading.risk_manager import SymbolSpecification
from trading.walk_forward import (
    WalkForwardEngine,
    WalkForwardConfig,
    WalkForwardWindowResult,
    AggregateOOSMetrics,
)


def create_mock_historical_data(count=1200, trend="up"):
    start_time = datetime(2026, 1, 1, 10, 0, 0)
    timestamps = [start_time + timedelta(minutes=5 * i) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        if trend == "up":
            price_offset = i * 0.00015
        elif trend == "down":
            price_offset = -i * 0.00015
        else:
            price_offset = np.sin(i / 15.0) * 0.0020

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
            "amount": amt,
        })

    return pd.DataFrame(data)


def create_mock_adapter():
    mock = MagicMock(spec=KronosAdapter)
    def fake_predict(df, symbol="EURUSD", timeframe="M5"):
        last_close = float(df.iloc[-1]["close"])
        pred_closes = np.linspace(last_close, last_close + 0.0030, 120).tolist()
        pred_res = PredictionResult(
            symbol=symbol,
            timestamp=datetime.now(),
            pred_len=120,
            predicted_close=pred_closes,
            predicted_open=pred_closes,
            predicted_high=[c + 0.0005 for c in pred_closes],
            predicted_low=[c - 0.0005 for c in pred_closes],
            predicted_volume=[150.0] * 120,
        )
        return pred_res, None
    mock.predict_forecast.side_effect = fake_predict
    return mock


def test_walk_forward_initialization_defaults():
    engine = WalkForwardEngine()
    assert engine.config.symbol == "EURUSD"
    assert engine.config.dev_window_bars == 500
    assert engine.config.oos_window_bars == 200
    assert engine.config.window_type == "rolling"


def test_insufficient_or_empty_data_handling():
    engine = WalkForwardEngine()

    # Empty
    agg_empty, wins_empty = engine.run_walk_forward(pd.DataFrame())
    assert agg_empty.total_windows == 0
    assert len(wins_empty) == 0

    # Short
    short_df = create_mock_historical_data(count=300)  # Needs dev(500) + oos(200) = 700
    agg_short, wins_short = engine.run_walk_forward(short_df)
    assert agg_short.total_windows == 0
    assert len(wins_short) == 0


def test_chronological_rolling_window_splits():
    cfg = WalkForwardConfig(dev_window_bars=500, oos_window_bars=200, step_bars=200)
    engine = WalkForwardEngine(config=cfg)
    df = create_mock_historical_data(count=1200)  # 1200 bars -> 3 windows (500+200, 700+200, 900+200)

    agg, windows = engine.run_walk_forward(df)

    assert len(windows) == 3
    assert agg.total_windows == 3
    assert windows[0].window_index == 1
    assert windows[1].window_index == 2
    assert windows[2].window_index == 3


def test_chronological_expanding_window_splits():
    cfg = WalkForwardConfig(
        dev_window_bars=500, oos_window_bars=200, step_bars=200, window_type="expanding"
    )
    engine = WalkForwardEngine(config=cfg)
    df = create_mock_historical_data(count=1100)

    agg, windows = engine.run_walk_forward(df)

    assert len(windows) == 2
    assert agg.total_windows == 2


def test_no_future_leakage_across_oos_windows():
    """
    DATA LEAKAGE TEST:
    Mutating future bars in OOS Window #2 MUST NOT alter decisions or metrics
    generated in OOS Window #1.
    """
    cfg = WalkForwardConfig(dev_window_bars=500, oos_window_bars=200, step_bars=200)

    # Dataset 1
    df1 = create_mock_historical_data(count=1100, trend="up")
    engine1 = WalkForwardEngine(config=cfg)
    agg1, wins1 = engine1.run_walk_forward(df1)

    # Dataset 2: Mutate data strictly in Window #2 OOS period (bars 900+)
    df2 = df1.copy()
    df2.loc[900:, "close"] = df2.loc[900:, "close"] - 0.0500

    engine2 = WalkForwardEngine(config=cfg)
    agg2, wins2 = engine2.run_walk_forward(df2)

    assert len(wins1) >= 2 and len(wins2) >= 2
    w1_win1 = wins1[0]
    w1_win2 = wins2[0]

    # Confirm Window #1 metrics and trades are 100% identical
    assert w1_win1.metrics.net_profit == w1_win2.metrics.net_profit
    assert w1_win1.metrics.total_trades == w1_win2.metrics.total_trades
    assert len(w1_win1.trade_logs) == len(w1_win2.trade_logs)


def test_walk_forward_reproducibility():
    """
    REPRODUCIBILITY TEST:
    Running walk-forward evaluation twice on identical datasets produces 100% identical aggregate metrics.
    """
    cfg = WalkForwardConfig(dev_window_bars=500, oos_window_bars=200, step_bars=200)
    df = create_mock_historical_data(count=1100, trend="up")

    engine1 = WalkForwardEngine(config=cfg)
    agg1, wins1 = engine1.run_walk_forward(df)

    engine2 = WalkForwardEngine(config=cfg)
    agg2, wins2 = engine2.run_walk_forward(df)

    assert agg1.total_windows == agg2.total_windows
    assert agg1.aggregate_net_profit == agg2.aggregate_net_profit
    assert agg1.total_oos_trades == agg2.total_oos_trades
    assert agg1.overall_profit_factor == agg2.overall_profit_factor


def test_aggregate_oos_metrics_computation():
    cfg = WalkForwardConfig(dev_window_bars=500, oos_window_bars=200, step_bars=200)
    engine = WalkForwardEngine(config=cfg)
    df = create_mock_historical_data(count=1100, trend="up")

    agg, windows = engine.run_walk_forward(df)

    assert isinstance(agg, AggregateOOSMetrics)
    assert agg.total_windows == len(windows)
    assert agg.profitable_windows + agg.losing_windows <= agg.total_windows
    assert 0.0 <= agg.window_win_rate_pct <= 100.0
    assert 0.0 <= agg.overall_trade_win_rate_pct <= 100.0
