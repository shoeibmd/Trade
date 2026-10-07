"""
Technical Indicator Engine for Astraea MT5.
Computes technical indicators (EMA, RSI, ATR, ADX) and deterministic market structure
using strictly causal (backward-looking) rolling calculations with zero future data leakage.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger("AstraeaMT5.Indicators")


class StructureState(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class MarketStructure:
    state: StructureState
    recent_swing_high: Optional[float] = None
    recent_swing_low: Optional[float] = None
    is_higher_high: Optional[bool] = None
    is_lower_low: Optional[bool] = None
    swing_high_time: Optional[pd.Timestamp] = None
    swing_low_time: Optional[pd.Timestamp] = None


class TechnicalIndicatorEngine:
    """
    Technical Indicator Engine operating exclusively on validated closed OHLCV bar DataFrames.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        ema_fast: int = 9,
        ema_slow: int = 21,
        ema_trend: int = 50,
        ema_baseline: int = 200,
        rsi_period: int = 14,
        adx_period: int = 14,
        atr_period: int = 14,
        swing_window: int = 5,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_trend = ema_trend
        self.ema_baseline = ema_baseline
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.swing_window = swing_window

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "indicators" in cfg:
                        icfg = cfg["indicators"]
                        self.ema_fast = icfg.get("ema_fast", self.ema_fast)
                        self.ema_slow = icfg.get("ema_slow", self.ema_slow)
                        self.ema_trend = icfg.get("ema_trend", self.ema_trend)
                        self.ema_baseline = icfg.get("ema_baseline", self.ema_baseline)
                        self.rsi_period = icfg.get("rsi_period", self.rsi_period)
                        self.adx_period = icfg.get("adx_period", self.adx_period)
                        self.atr_period = icfg.get("atr_period", self.atr_period)
                        self.swing_window = icfg.get("swing_window", self.swing_window)
            except Exception as e:
                logger.error(f"Failed to load indicator config from {config_path}: {e}")

    @staticmethod
    def compute_ema(series: pd.Series, period: int) -> pd.Series:
        """Computes Exponential Moving Average (EMA). Warm-up: First (period-1) rows are NaN."""
        if len(series) < period:
            return pd.Series(np.nan, index=series.index)

        ema = series.ewm(span=period, adjust=False).mean()
        # Enforce explicit NaN during initial warm-up period
        ema.iloc[: period - 1] = np.nan
        return ema

    @staticmethod
    def compute_rsi(close_series: pd.Series, period: int = 14) -> pd.Series:
        """Computes Relative Strength Index (RSI) with Wilder's smoothing."""
        if len(close_series) < period + 1:
            return pd.Series(np.nan, index=close_series.index)

        delta = close_series.diff()
        gain = delta.clip(lower=0)
        loss = -1.0 * delta.clip(upper=0)

        # Wilder's exponential smoothing (alpha = 1 / period)
        avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Enforce explicit NaN warm-up
        rsi.iloc[:period] = np.nan
        return rsi

    @staticmethod
    def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Computes Average True Range (ATR) with Wilder's smoothing."""
        if len(close) < period + 1:
            return pd.Series(np.nan, index=close.index)

        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

        # Enforce explicit NaN warm-up
        atr.iloc[:period] = np.nan
        return atr

    @staticmethod
    def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Computes Average Directional Index (ADX), +DI, and -DI using Wilder's smoothing.
        Returns: (ADX, Plus_DI, Minus_DI)
        """
        if len(close) < period * 2:
            nan_s = pd.Series(np.nan, index=close.index)
            return nan_s, nan_s, nan_s

        up_move = high.diff()
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        plus_dm = pd.Series(plus_dm, index=close.index)
        minus_dm = pd.Series(minus_dm, index=close.index)

        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

        smooth_tr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        smooth_plus_dm = plus_dm.ewm(alpha=1.0 / period, adjust=False).mean()
        smooth_minus_dm = minus_dm.ewm(alpha=1.0 / period, adjust=False).mean()

        plus_di = 100.0 * (smooth_plus_dm / (smooth_tr + 1e-10))
        minus_di = 100.0 * (smooth_minus_dm / (smooth_tr + 1e-10))

        dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

        # Enforce explicit NaN warm-up
        plus_di.iloc[:period] = np.nan
        minus_di.iloc[:period] = np.nan
        adx.iloc[: period * 2 - 1] = np.nan

        return adx, plus_di, minus_di

    def compute_market_structure(self, df: pd.DataFrame) -> MarketStructure:
        """
        Computes causal market structure (swing highs, swing lows, higher-highs, lower-lows)
        using only confirmed past bars up to the current bar.
        """
        w = self.swing_window
        if df is None or len(df) < w * 2 + 1:
            return MarketStructure(state=StructureState.NEUTRAL)

        highs = df["high"].values
        lows = df["low"].values
        timestamps = pd.to_datetime(df["timestamps"]).tolist()
        n = len(df)

        swing_highs = []
        swing_lows = []

        # Identify swing points causally (confirmed at least `w` bars after pivot)
        for i in range(w, n - w):
            # Check swing high
            if highs[i] == max(highs[i - w : i + w + 1]):
                swing_highs.append((timestamps[i], highs[i]))
            # Check swing low
            if lows[i] == min(lows[i - w : i + w + 1]):
                swing_lows.append((timestamps[i], lows[i]))

        recent_sh = swing_highs[-1][1] if swing_highs else None
        recent_sh_time = swing_highs[-1][0] if swing_highs else None
        recent_sl = swing_lows[-1][1] if swing_lows else None
        recent_sl_time = swing_lows[-1][0] if swing_lows else None

        is_hh = None
        if len(swing_highs) >= 2:
            is_hh = swing_highs[-1][1] > swing_highs[-2][1]

        is_ll = None
        if len(swing_lows) >= 2:
            is_ll = swing_lows[-1][1] < swing_lows[-2][1]

        # Determine structural state
        if is_hh is True and (is_ll is False or is_ll is None):
            state = StructureState.BULLISH
        elif is_ll is True and (is_hh is False or is_hh is None):
            state = StructureState.BEARISH
        else:
            state = StructureState.NEUTRAL

        return MarketStructure(
            state=state,
            recent_swing_high=recent_sh,
            recent_swing_low=recent_sl,
            is_higher_high=is_hh,
            is_lower_low=is_ll,
            swing_high_time=recent_sh_time,
            swing_low_time=recent_sl_time,
        )

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Accepts validated market DataFrame and appends technical indicators.
        Preserves original OHLCV schema without future data leakage.
        """
        if df is None or not isinstance(df, pd.DataFrame) or len(df) == 0:
            raise ValueError("Input DataFrame is empty or None.")

        req_cols = ["open", "high", "low", "close", "timestamps"]
        for col in req_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column for indicator calculation: {col}")

        out_df = df.copy()

        # Compute EMAs
        out_df[f"ema_{self.ema_fast}"] = self.compute_ema(out_df["close"], self.ema_fast)
        out_df[f"ema_{self.ema_slow}"] = self.compute_ema(out_df["close"], self.ema_slow)
        out_df[f"ema_{self.ema_trend}"] = self.compute_ema(out_df["close"], self.ema_trend)
        out_df[f"ema_{self.ema_baseline}"] = self.compute_ema(out_df["close"], self.ema_baseline)

        # Compute RSI
        out_df[f"rsi_{self.rsi_period}"] = self.compute_rsi(out_df["close"], self.rsi_period)

        # Compute ATR
        out_df[f"atr_{self.atr_period}"] = self.compute_atr(out_df["high"], out_df["low"], out_df["close"], self.atr_period)

        # Compute ADX, +DI, -DI
        adx_s, plus_di_s, minus_di_s = self.compute_adx(out_df["high"], out_df["low"], out_df["close"], self.adx_period)
        out_df[f"adx_{self.adx_period}"] = adx_s
        out_df[f"plus_di_{self.adx_period}"] = plus_di_s
        out_df[f"minus_di_{self.adx_period}"] = minus_di_s

        # Compute Market Structure for latest bar
        struct = self.compute_market_structure(out_df)
        out_df["market_structure_state"] = struct.state.value

        return out_df
