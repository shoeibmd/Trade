"""
Astraea MT5 Signal Engine.
Combines Kronos AI foundation model forecasts, technical indicators, trend filters,
and market structure to generate deterministic BUY, SELL, or NO_TRADE signal decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yaml

from trading.models import PredictionResult, SignalType
from trading.indicators import TechnicalIndicatorEngine, StructureState

logger = logging.getLogger("AstraeaMT5.SignalEngine")


@dataclass
class SignalResult:
    symbol: str
    timeframe: str
    timestamp: datetime
    signal: SignalType
    signal_score: float
    bullish_score: float
    bearish_score: float
    minimum_signal_score: float
    kronos_score: float = 0.0
    trend_score: float = 0.0
    ema_score: float = 0.0
    rsi_score: float = 0.0
    adx_score: float = 0.0
    market_structure_score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    indicator_snapshot: Dict[str, Any] = field(default_factory=dict)
    forecast_summary: Dict[str, Any] = field(default_factory=dict)


class SignalEngine:
    """
    Evaluates evidence from foundation forecasts and technical indicators to issue
    BUY, SELL, or NO_TRADE decisions with full explainability.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        minimum_signal_score: float = 70.0,
        weight_kronos: float = 35.0,
        weight_trend: float = 20.0,
        weight_ema: float = 15.0,
        weight_rsi: float = 10.0,
        weight_adx: float = 10.0,
        weight_market_structure: float = 10.0,
    ):
        self.minimum_signal_score = minimum_signal_score
        self.w_kronos = weight_kronos
        self.w_trend = weight_trend
        self.w_ema = weight_ema
        self.w_rsi = weight_rsi
        self.w_adx = weight_adx
        self.w_ms = weight_market_structure

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "signal" in cfg:
                        scfg = cfg["signal"]
                        self.minimum_signal_score = scfg.get("minimum_signal_score", self.minimum_signal_score)
                        weights = scfg.get("weights", {})
                        self.w_kronos = weights.get("kronos", self.w_kronos)
                        self.w_trend = weights.get("trend", self.w_trend)
                        self.w_ema = weights.get("ema", self.w_ema)
                        self.w_rsi = weights.get("rsi", self.w_rsi)
                        self.w_adx = weights.get("adx", self.w_adx)
                        self.w_ms = weights.get("market_structure", self.w_ms)
            except Exception as e:
                logger.error(f"Failed to parse signal engine config from {config_path}: {e}")

    def evaluate_signal(
        self,
        indicator_df: pd.DataFrame,
        forecast: Optional[PredictionResult] = None,
        symbol: str = "EURUSD",
        timeframe: str = "M5",
    ) -> SignalResult:
        """
        Evaluates indicator DataFrame and Kronos prediction result to produce a SignalResult.
        """
        now = datetime.now()
        reasons = []

        # Ensure valid DataFrame
        if indicator_df is None or len(indicator_df) == 0:
            return SignalResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=now,
                signal=SignalType.HOLD,
                signal_score=0.0,
                bullish_score=0.0,
                bearish_score=0.0,
                minimum_signal_score=self.minimum_signal_score,
                reasons=["NO_TRADE: Market data DataFrame is empty or None."],
            )

        last_bar = indicator_df.iloc[-1]
        close_last = float(last_bar["close"])

        bull_score = 0.0
        bear_score = 0.0

        # Component 1: Kronos Forecast (Weight: 35)
        kronos_bull = 0.0
        kronos_bear = 0.0
        forecast_summary = {}

        if forecast is not None and forecast.predicted_close and len(forecast.predicted_close) > 0:
            pred_mean_close = float(np.mean(forecast.predicted_close))
            price_change_pct = (pred_mean_close - close_last) / (close_last + 1e-10)

            forecast_summary = {
                "pred_len": forecast.pred_len,
                "pred_mean_close": pred_mean_close,
                "price_change_pct": price_change_pct,
                "model_name": forecast.metadata.get("model_name", "Kronos"),
            }

            if price_change_pct >= 0.0005:  # +5 pips or +0.05%
                kronos_bull = self.w_kronos
                reasons.append(f"Kronos forecast: Bullish directional bias ({price_change_pct*100:+.3f}% predicted change).")
            elif price_change_pct <= -0.0005:  # -5 pips or -0.05%
                kronos_bear = self.w_kronos
                reasons.append(f"Kronos forecast: Bearish directional bias ({price_change_pct*100:+.3f}% predicted change).")
            else:
                reasons.append(f"Kronos forecast: Neutral bias ({price_change_pct*100:+.3f}% change below threshold).")
        else:
            reasons.append("NO_TRADE: Missing or empty Kronos foundation forecast.")

        bull_score += kronos_bull
        bear_score += kronos_bear

        # Component 2: Trend Alignment (Weight: 20)
        trend_bull = 0.0
        trend_bear = 0.0
        ema_50 = last_bar.get("ema_50")
        ema_200 = last_bar.get("ema_200")

        if pd.notnull(ema_50) and pd.notnull(ema_200):
            ema_50_val = float(ema_50)
            ema_200_val = float(ema_200)

            if close_last > ema_50_val > ema_200_val:
                trend_bull = self.w_trend
                reasons.append(f"Trend Alignment: Bullish (Close > EMA 50 > EMA 200).")
            elif close_last < ema_50_val < ema_200_val:
                trend_bear = self.w_trend
                reasons.append(f"Trend Alignment: Bearish (Close < EMA 50 < EMA 200).")
            else:
                reasons.append("Trend Alignment: Neutral / mixed EMA 50 & 200 arrangement.")

        bull_score += trend_bull
        bear_score += trend_bear

        # Component 3: EMA Crossover / Alignment (Weight: 15)
        ema_c_bull = 0.0
        ema_c_bear = 0.0
        ema_9 = last_bar.get("ema_9")
        ema_21 = last_bar.get("ema_21")

        if pd.notnull(ema_9) and pd.notnull(ema_21):
            ema_9_val = float(ema_9)
            ema_21_val = float(ema_21)

            if ema_9_val > ema_21_val:
                ema_c_bull = self.w_ema
                reasons.append(f"EMA Alignment: Bullish (EMA 9 > EMA 21).")
            elif ema_9_val < ema_21_val:
                ema_c_bear = self.w_ema
                reasons.append(f"EMA Alignment: Bearish (EMA 9 < EMA 21).")

        bull_score += ema_c_bull
        bear_score += ema_c_bear

        # Component 4: RSI Momentum (Weight: 10)
        rsi_bull = 0.0
        rsi_bear = 0.0
        rsi_14 = last_bar.get("rsi_14")

        if pd.notnull(rsi_14):
            rsi_val = float(rsi_14)
            if 50.0 <= rsi_val < 70.0:
                rsi_bull = self.w_rsi
                reasons.append(f"RSI Momentum: Bullish ({rsi_val:.1f} in 50-70 zone).")
            elif 30.0 < rsi_val <= 50.0:
                rsi_bear = self.w_rsi
                reasons.append(f"RSI Momentum: Bearish ({rsi_val:.1f} in 30-50 zone).")
            elif rsi_val >= 70.0:
                reasons.append(f"RSI Momentum: Caution - Overbought ({rsi_val:.1f} >= 70).")
            elif rsi_val <= 30.0:
                reasons.append(f"RSI Momentum: Caution - Oversold ({rsi_val:.1f} <= 30).")

        bull_score += rsi_bull
        bear_score += rsi_bear

        # Component 5: ADX Trend Strength (Weight: 10)
        adx_bull = 0.0
        adx_bear = 0.0
        adx_14 = last_bar.get("adx_14")
        plus_di = last_bar.get("plus_di_14")
        minus_di = last_bar.get("minus_di_14")

        if pd.notnull(adx_14) and pd.notnull(plus_di) and pd.notnull(minus_di):
            adx_val = float(adx_14)
            p_di_val = float(plus_di)
            m_di_val = float(minus_di)

            if adx_val >= 20.0:
                if p_di_val > m_di_val:
                    adx_bull = self.w_adx
                    reasons.append(f"ADX Strength: Bullish (ADX={adx_val:.1f} >= 20, +DI > -DI).")
                elif m_di_val > p_di_val:
                    adx_bear = self.w_adx
                    reasons.append(f"ADX Strength: Bearish (ADX={adx_val:.1f} >= 20, -DI > +DI).")
            else:
                reasons.append(f"ADX Strength: Weak trend (ADX={adx_val:.1f} < 20).")

        bull_score += adx_bull
        bear_score += adx_bear

        # Component 6: Market Structure (Weight: 10)
        ms_bull = 0.0
        ms_bear = 0.0
        ms_state = last_bar.get("market_structure_state", "NEUTRAL")

        if ms_state == StructureState.BULLISH.value:
            ms_bull = self.w_ms
            reasons.append("Market Structure: Bullish (Higher-High confirmed).")
        elif ms_state == StructureState.BEARISH.value:
            ms_bear = self.w_ms
            reasons.append("Market Structure: Bearish (Lower-Low confirmed).")
        else:
            reasons.append("Market Structure: Neutral structure.")

        bull_score += ms_bull
        bear_score += ms_bear

        # Determine Final Decision & Highest Signal Score
        signal_score = max(bull_score, bear_score)

        if bull_score >= self.minimum_signal_score and bull_score >= bear_score + 15.0:
            final_signal = SignalType.BUY
            reasons.insert(0, f"BUY Signal Approved: Bullish score {bull_score:.1f} >= threshold {self.minimum_signal_score:.1f}.")
        elif bear_score >= self.minimum_signal_score and bear_score >= bull_score + 15.0:
            final_signal = SignalType.SELL
            reasons.insert(0, f"SELL Signal Approved: Bearish score {bear_score:.1f} >= threshold {self.minimum_signal_score:.1f}.")
        else:
            final_signal = SignalType.HOLD  # NO_TRADE
            reasons.insert(0, f"NO_TRADE: Signal score {signal_score:.1f} below threshold {self.minimum_signal_score:.1f} or evidence conflicting (Bull: {bull_score:.1f}, Bear: {bear_score:.1f}).")

        indicator_snapshot = {
            "close": close_last,
            "ema_9": float(last_bar["ema_9"]) if pd.notnull(last_bar.get("ema_9")) else None,
            "ema_21": float(last_bar["ema_21"]) if pd.notnull(last_bar.get("ema_21")) else None,
            "ema_50": float(last_bar["ema_50"]) if pd.notnull(last_bar.get("ema_50")) else None,
            "ema_200": float(last_bar["ema_200"]) if pd.notnull(last_bar.get("ema_200")) else None,
            "rsi_14": float(last_bar["rsi_14"]) if pd.notnull(last_bar.get("rsi_14")) else None,
            "adx_14": float(last_bar["adx_14"]) if pd.notnull(last_bar.get("adx_14")) else None,
            "atr_14": float(last_bar["atr_14"]) if pd.notnull(last_bar.get("atr_14")) else None,
            "market_structure_state": ms_state,
        }

        return SignalResult(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=now,
            signal=final_signal,
            signal_score=signal_score,
            bullish_score=bull_score,
            bearish_score=bear_score,
            minimum_signal_score=self.minimum_signal_score,
            kronos_score=max(kronos_bull, kronos_bear),
            trend_score=max(trend_bull, trend_bear),
            ema_score=max(ema_c_bull, ema_c_bear),
            rsi_score=max(rsi_bull, rsi_bear),
            adx_score=max(adx_bull, adx_bear),
            market_structure_score=max(ms_bull, ms_bear),
            reasons=reasons,
            indicator_snapshot=indicator_snapshot,
            forecast_summary=forecast_summary,
        )
