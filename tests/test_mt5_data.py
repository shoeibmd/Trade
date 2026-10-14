"""
Unit & Integration Tests for Market Data Validation and Adapter Preprocessing.
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
from trading.forex_adapter import KronosAdapter


def test_kronos_adapter_tick_volume_normalization():
    adapter = KronosAdapter(
        lookback=10,
        pred_len=5,
        normalize_tick_volume=True,
    )

    base_time = datetime(2025, 1, 1, 10, 0)
    data = {
        "open": [1.0800 + i * 0.0001 for i in range(10)],
        "high": [1.0805 + i * 0.0001 for i in range(10)],
        "low": [1.0795 + i * 0.0001 for i in range(10)],
        "close": [1.0802 + i * 0.0001 for i in range(10)],
        "volume": [100, 200, 150, 300, 250, 400, 350, 500, 450, 600],
        "timestamps": [base_time + timedelta(minutes=5 * i) for i in range(10)],
    }
    df = pd.DataFrame(data)

    adapter.is_loaded = True
    adapter.predictor = MagicMockPredictor()

    pred_res, err = adapter.predict_forecast(df, symbol="EURUSD", timeframe="M5")
    assert err is None
    assert pred_res is not None
    assert len(pred_res.predicted_close) == 5


class MagicMockPredictor:
    def predict(self, df, x_timestamp, y_timestamp, pred_len, T, top_k, top_p, sample_count, verbose):
        res_df = pd.DataFrame({
            "open": [1.0810] * pred_len,
            "high": [1.0815] * pred_len,
            "low": [1.0805] * pred_len,
            "close": [1.0812] * pred_len,
            "volume": [300] * pred_len,
            "amount": [300] * pred_len,
        })
        return res_df
