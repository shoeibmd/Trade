from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from trading.mt5_connection import MT5Connection, ConnectionState
from trading.mt5_data import MT5DataEngine, ValidationResult


def create_sample_rates_array(count=400, start_time=None, timeframe_min=5, malformed_ohlc=False, duplicates=False, unordered=False):
    if start_time is None:
        start_time = datetime(2026, 1, 1, 10, 0, 0)

    times = [int((start_time + timedelta(minutes=i * timeframe_min)).timestamp()) for i in range(count)]

    if duplicates and len(times) > 2:
        times[2] = times[1]

    if unordered and len(times) > 3:
        times[2], times[3] = times[3], times[2]

    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]

    rates = np.zeros(count, dtype=dtype)
    base_price = 1.0850

    for i in range(count):
        o = base_price + (i % 10) * 0.0001
        c = o + 0.0002
        if malformed_ohlc and i == 5:
            h = o - 0.0010  # Invalid: High < Open/Low
            l = o + 0.0010
        else:
            h = max(o, c) + 0.0005
            l = min(o, c) - 0.0005

        rates[i] = (times[i], o, h, l, c, 100 + i, 10, 0)

    return rates


def test_validation_successful():
    engine = MT5DataEngine()
    rates = create_sample_rates_array(count=400)
    df = pd.DataFrame(rates)
    df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["volume"] = df["tick_volume"]

    val_res = engine.validate_bar_dataframe(df, expected_count=400, expected_timeframe="M5")
    assert val_res.is_valid is True
    assert val_res.row_count == 400
    assert len(val_res.errors) == 0


def test_validation_insufficient_count():
    engine = MT5DataEngine()
    rates = create_sample_rates_array(count=350)
    df = pd.DataFrame(rates)
    df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)

    val_res = engine.validate_bar_dataframe(df, expected_count=400, expected_timeframe="M5")
    assert val_res.is_valid is False
    assert any("Insufficient candle count" in err for err in val_res.errors)


def test_validation_malformed_ohlc():
    engine = MT5DataEngine()
    rates = create_sample_rates_array(count=400, malformed_ohlc=True)
    df = pd.DataFrame(rates)
    df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)

    val_res = engine.validate_bar_dataframe(df, expected_count=400, expected_timeframe="M5")
    assert val_res.is_valid is False
    assert any("invalid OHLC relationship" in err for err in val_res.errors)


def test_validation_duplicate_timestamps():
    engine = MT5DataEngine()
    rates = create_sample_rates_array(count=400, duplicates=True)
    df = pd.DataFrame(rates)
    df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)

    val_res = engine.validate_bar_dataframe(df, expected_count=400, expected_timeframe="M5")
    assert val_res.is_valid is False
    assert any("duplicate timestamps" in err for err in val_res.errors)


def test_validation_unordered_timestamps():
    engine = MT5DataEngine()
    rates = create_sample_rates_array(count=400, unordered=True)
    df = pd.DataFrame(rates)
    df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)

    val_res = engine.validate_bar_dataframe(df, expected_count=400, expected_timeframe="M5")
    assert val_res.is_valid is False
    assert any("ascending chronological order" in err for err in val_res.errors)


def test_get_closed_bars_mocked_success_and_forming_bar_exclusion():
    mock_conn = MagicMock(spec=MT5Connection)
    mock_conn.state = ConnectionState.CONNECTED
    mock_conn.check_symbol.return_value = True

    mock_mt5 = MagicMock()
    mock_mt5.TIMEFRAME_M5 = 5
    sample_rates = create_sample_rates_array(count=400)
    mock_mt5.copy_rates_from_pos.return_value = sample_rates

    with patch("trading.mt5_data.MT5_AVAILABLE", True), patch("trading.mt5_data.mt5", mock_mt5):
        engine = MT5DataEngine(mt5_connection=mock_conn)
        df, val_res = engine.get_closed_bars(symbol="EURUSD", timeframe="M5", count=400)

        assert df is not None
        assert val_res.is_valid is True
        assert len(df) == 400

        # Verify closed-bar guarantee: copy_rates_from_pos called with start_pos=1 (excluding active forming bar pos=0)
        mock_mt5.copy_rates_from_pos.assert_called_once_with("EURUSD", 5, 1, 400)


def test_get_closed_bars_empty_response():
    mock_conn = MagicMock(spec=MT5Connection)
    mock_conn.state = ConnectionState.CONNECTED
    mock_conn.check_symbol.return_value = True

    mock_mt5 = MagicMock()
    mock_mt5.TIMEFRAME_M5 = 5
    mock_mt5.copy_rates_from_pos.return_value = None
    mock_mt5.last_error.return_value = (-1, "No data available")

    with patch("trading.mt5_data.MT5_AVAILABLE", True), patch("trading.mt5_data.mt5", mock_mt5):
        engine = MT5DataEngine(mt5_connection=mock_conn)
        df, val_res = engine.get_closed_bars(symbol="EURUSD", timeframe="M5", count=400)

        assert df is None
        assert val_res.is_valid is False
        assert any("returned empty rates" in err for err in val_res.errors)


def test_get_closed_bars_missing_mt5_package():
    with patch("trading.mt5_data.MT5_AVAILABLE", False):
        engine = MT5DataEngine()
        df, val_res = engine.get_closed_bars("EURUSD", "M5", 400)
        assert df is None
        assert val_res.is_valid is False
        assert any("package is not installed" in err for err in val_res.errors)
