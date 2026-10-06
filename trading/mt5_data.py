"""
Market Data Engine for Astraea MT5.
Fetches, validates, and cleans Forex market K-line data from MetaTrader 5.
Enforces closed-candle guarantees and 400-bar history requirements.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from trading.mt5_connection import MT5Connection, ConnectionState, MT5_AVAILABLE, mt5

logger = logging.getLogger("AstraeaMT5.MarketData")


class DataValidationError(Exception):
    """Raised when market data fails critical validation rules."""
    pass


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    row_count: int = 0
    valid_row_count: int = 0
    invalid_rows: int = 0
    gap_count: int = 0
    first_timestamp: Optional[pd.Timestamp] = None
    last_timestamp: Optional[pd.Timestamp] = None


class MT5DataEngine:
    """
    Market Data Engine responsible for fetching and validating closed Forex candles.
    """

    TIMEFRAME_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }

    def __init__(self, mt5_connection: Optional[MT5Connection] = None):
        self.connection = mt5_connection or MT5Connection()

    def _get_mt5_timeframe(self, tf_str: str) -> Optional[int]:
        if not MT5_AVAILABLE or mt5 is None:
            return None

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return tf_map.get(tf_str.upper())

    def get_closed_bars(
        self, symbol: str = "EURUSD", timeframe: str = "M5", count: int = 400
    ) -> Tuple[Optional[pd.DataFrame], ValidationResult]:
        """
        Retrieves exactly `count` closed candles from MT5, excluding the current forming bar.

        Closed-Candle Guarantee:
        In MT5 `copy_rates_from_pos(symbol, timeframe, start_pos, count)`, position 0 is the active,
        currently forming/unclosed bar. By passing `start_pos = 1`, position 0 is explicitly bypassed,
        guaranteeing that only completed/closed bars are returned.
        """
        if count <= 0:
            val_res = ValidationResult(is_valid=False, errors=[f"Invalid candle count requested: {count}"])
            return None, val_res

        # Verify MT5 availability
        if not MT5_AVAILABLE:
            msg = "MetaTrader5 Python package is not installed."
            logger.error(msg)
            val_res = ValidationResult(is_valid=False, errors=[msg])
            return None, val_res

        # Ensure connection
        if self.connection.state not in (ConnectionState.INITIALIZED, ConnectionState.CONNECTED):
            ok, msg = self.connection.connect()
            if not ok:
                val_res = ValidationResult(is_valid=False, errors=[f"MT5 Connection failed: {msg}"])
                return None, val_res

        # Ensure symbol is visible
        if not self.connection.check_symbol(symbol):
            msg = f"Symbol {symbol} is not available in MT5."
            logger.error(msg)
            val_res = ValidationResult(is_valid=False, errors=[msg])
            return None, val_res

        mt5_tf = self._get_mt5_timeframe(timeframe)
        if mt5_tf is None:
            msg = f"Unsupported MT5 timeframe: {timeframe}"
            logger.error(msg)
            val_res = ValidationResult(is_valid=False, errors=[msg])
            return None, val_res

        # Fetch rates starting from pos=1 (bypassing forming bar pos=0)
        logger.info(f"Fetching {count} closed {timeframe} candles for {symbol} starting at pos=1 (bypassing forming candle)...")
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 1, count)

        if rates is None or len(rates) == 0:
            err_code, err_msg = mt5.last_error()
            msg = f"MT5 API returned empty rates for {symbol} ({timeframe}). Error [{err_code}]: {err_msg}"
            logger.error(msg)
            val_res = ValidationResult(is_valid=False, errors=[msg])
            return None, val_res

        # Convert structured numpy array to pandas DataFrame
        df = pd.DataFrame(rates)

        # Standardize timestamp column
        if "time" in df.columns:
            df["timestamps"] = pd.to_datetime(df["time"], unit="s", utc=True)

        # Handle volume distinctions
        if "tick_volume" in df.columns:
            df["volume"] = df["tick_volume"].astype(np.float64)
        elif "volume" in df.columns:
            df["volume"] = df["volume"].astype(np.float64)
        else:
            df["volume"] = 0.0

        if "real_volume" in df.columns:
            df["amount"] = df["real_volume"].astype(np.float64)
        else:
            df["amount"] = df["volume"] * df[["open", "high", "low", "close"]].mean(axis=1)

        # Validate DataFrame
        val_res = self.validate_bar_dataframe(df, expected_count=count, expected_timeframe=timeframe)

        if not val_res.is_valid:
            logger.error(f"Market data validation failed for {symbol}: {val_res.errors}")
            return None, val_res

        required_cols = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
        opt_cols = [c for c in ["tick_volume", "real_volume", "spread"] if c in df.columns]
        output_df = df[required_cols + opt_cols].copy()

        logger.info(
            f"Successfully retrieved and validated {len(output_df)} closed {timeframe} candles for {symbol}. "
            f"Range: {val_res.first_timestamp} to {val_res.last_timestamp}"
        )
        return output_df, val_res

    def validate_bar_dataframe(
        self, df: pd.DataFrame, expected_count: int = 400, expected_timeframe: str = "M5"
    ) -> ValidationResult:
        """
        Validates OHLC relationships, data completeness, strict timestamp ordering, duplicate absence,
        and gap detection.
        """
        errors = []
        warnings = []

        if df is None or not isinstance(df, pd.DataFrame) or len(df) == 0:
            return ValidationResult(is_valid=False, errors=["DataFrame is empty or None."])

        # Check required columns
        req_cols = ["open", "high", "low", "close", "timestamps"]
        for col in req_cols:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, row_count=len(df))

        # Check exact requested bar count
        if len(df) < expected_count:
            errors.append(f"Insufficient candle count: expected at least {expected_count}, got {len(df)}.")

        # Check NaN values
        check_cols = [c for c in ["open", "high", "low", "close", "volume", "tick_volume"] if c in df.columns]
        nan_count = df[check_cols].isnull().sum().sum()
        if nan_count > 0:
            errors.append(f"DataFrame contains {nan_count} NaN values in price/volume columns.")

        # Validate numeric OHLC logical relationships
        invalid_ohlc = (
            (df["high"] < df["low"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )
        invalid_count = invalid_ohlc.sum()
        if invalid_count > 0:
            errors.append(f"Found {invalid_count} rows with invalid OHLC relationship (e.g. High < Low or Low > Open/Close).")

        # Validate timestamps ordering & uniqueness
        timestamps = pd.to_datetime(df["timestamps"])
        if not timestamps.is_monotonic_increasing:
            errors.append("Timestamps are not strictly in ascending chronological order.")

        duplicate_ts = timestamps.duplicated().sum()
        if duplicate_ts > 0:
            errors.append(f"Found {duplicate_ts} duplicate timestamps.")

        # Gap detection
        gap_count = 0
        if len(timestamps) > 1 and expected_timeframe.upper() in self.TIMEFRAME_MINUTES:
            tf_min = int(self.TIMEFRAME_MINUTES[expected_timeframe.upper()])
            time_diffs = timestamps.diff().iloc[1:]
            expected_delta = pd.Timedelta(minutes=tf_min)

            # Allow weekend/market closure gaps, but flag intra-week gaps (> 1.5 * expected_delta)
            gaps = time_diffs[time_diffs > expected_delta * 1.5]
            gap_count = len(gaps)
            if gap_count > 0:
                warnings.append(f"Detected {gap_count} potential timestamp gaps exceeding timeframe interval ({expected_timeframe}).")

        is_valid = len(errors) == 0
        first_ts = timestamps.iloc[0] if len(timestamps) > 0 else None
        last_ts = timestamps.iloc[-1] if len(timestamps) > 0 else None

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            row_count=len(df),
            valid_row_count=len(df) - invalid_count,
            invalid_rows=invalid_count,
            gap_count=gap_count,
            first_timestamp=first_ts,
            last_timestamp=last_ts,
        )
