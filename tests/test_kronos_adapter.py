from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from trading.kronos_adapter import KronosAdapter
from trading.models import PredictionResult


def create_sample_bars_df(count=400, start_time=None, timeframe_min=5):
    if start_time is None:
        start_time = datetime(2026, 1, 1, 10, 0, 0)

    timestamps = [start_time + timedelta(minutes=i * timeframe_min) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        o = base_price + (i % 10) * 0.0001
        c = o + 0.0002
        h = max(o, c) + 0.0005
        l = min(o, c) - 0.0005
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


def test_adapter_initialization_defaults():
    adapter = KronosAdapter()
    assert adapter.model_name == "NeoQuasar/Kronos-small"
    assert adapter.tokenizer_name == "NeoQuasar/Kronos-Tokenizer-base"
    assert adapter.device == "cpu"
    assert adapter.max_context == 512
    assert adapter.lookback == 400
    assert adapter.pred_len == 120
    assert adapter.is_loaded is False


def test_adapter_insufficient_candles_rejection():
    adapter = KronosAdapter(lookback=400)
    df_short = create_sample_bars_df(count=300)

    # Mock load_model so it doesn't fail
    adapter.is_loaded = True
    adapter.predictor = MagicMock()

    pred_res, err = adapter.predict_forecast(df_short, symbol="EURUSD", timeframe="M5")
    assert pred_res is None
    assert "Insufficient closed candles" in err


def test_adapter_missing_required_column_rejection():
    adapter = KronosAdapter()
    df_invalid = create_sample_bars_df(count=400).drop(columns=["close"])

    adapter.is_loaded = True
    adapter.predictor = MagicMock()

    pred_res, err = adapter.predict_forecast(df_invalid, symbol="EURUSD", timeframe="M5")
    assert pred_res is None
    assert "Missing required column" in err


def test_adapter_mocked_prediction_success():
    adapter = KronosAdapter(lookback=400, pred_len=120)
    df = create_sample_bars_df(count=400)

    # Prepare mock predictor
    pred_timestamps = pd.date_range(start=datetime(2026, 1, 2, 20, 0, 0), periods=120, freq="5min")
    mock_pred_df = pd.DataFrame({
        "open": np.full(120, 1.0860),
        "high": np.full(120, 1.0870),
        "low": np.full(120, 1.0850),
        "close": np.full(120, 1.0865),
        "volume": np.full(120, 150.0),
        "amount": np.full(120, 150.0 * 1.0860)
    }, index=pred_timestamps)

    mock_predictor = MagicMock()
    mock_predictor.predict.return_value = mock_pred_df

    adapter.is_loaded = True
    adapter.predictor = mock_predictor

    pred_res, err = adapter.predict_forecast(df, symbol="EURUSD", timeframe="M5")

    assert err is None
    assert pred_res is not None
    assert isinstance(pred_res, PredictionResult)
    assert pred_res.symbol == "EURUSD"
    assert pred_res.pred_len == 120
    assert len(pred_res.predicted_close) == 120
    assert pred_res.predicted_close[0] == 1.0865
    assert pred_res.metadata["timeframe"] == "M5"


def test_real_kronos_model_inference():
    """
    REAL KRONOS MODEL INFERENCE TEST:
    Executes actual Kronos-small model inference on 400 closed M5 candles.
    """
    adapter = KronosAdapter(
        model_name="NeoQuasar/Kronos-small",
        tokenizer_name="NeoQuasar/Kronos-Tokenizer-base",
        device="cpu",
        lookback=400,
        pred_len=120
    )

    ok, msg = adapter.load_model()
    assert ok is True, f"Failed to load real Kronos model: {msg}"
    assert adapter.is_loaded is True

    df = create_sample_bars_df(count=400)
    pred_res, err = adapter.predict_forecast(df, symbol="EURUSD", timeframe="M5")

    assert err is None, f"Real model forecast failed: {err}"
    assert pred_res is not None
    assert pred_res.symbol == "EURUSD"
    assert pred_res.pred_len == 120
    assert len(pred_res.predicted_close) == 120
    assert len(pred_res.predicted_open) == 120
    assert len(pred_res.predicted_high) == 120
    assert len(pred_res.predicted_low) == 120

    # Validate output OHLC numeric integrity and non-NaN values
    closes = np.array(pred_res.predicted_close)
    highs = np.array(pred_res.predicted_high)
    lows = np.array(pred_res.predicted_low)

    assert not np.isnan(closes).any(), "Predicted close prices contain NaNs"
    assert (highs >= lows).all(), "Predicted High prices are less than Low prices"
    assert "latency_sec" in pred_res.metadata
    assert pred_res.metadata["latency_sec"] > 0
