"""
Kronos Forecasting Adapter for Astraea MT5.
Orchestrates the existing Kronos foundation model (Kronos, KronosTokenizer, KronosPredictor)
and adapts validated MT5 market bar DataFrames into structured PredictionResults.
"""

from datetime import datetime, timedelta
import logging
from pathlib import Path
import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd
import torch
import yaml

from model import Kronos, KronosTokenizer, KronosPredictor
from trading.models import PredictionResult

logger = logging.getLogger("AstraeaMT5.KronosAdapter")


class KronosAdapterError(Exception):
    """Raised when adapter validation or model prediction fails."""
    pass


class KronosAdapter:
    """
    Application-level adapter connecting Astraea MT5 to the underlying Kronos foundation model.
    """

    TIMEFRAME_DELTAS = {
        "M1": timedelta(minutes=1),
        "M5": timedelta(minutes=5),
        "M15": timedelta(minutes=15),
        "M30": timedelta(minutes=30),
        "H1": timedelta(hours=1),
        "H4": timedelta(hours=4),
        "D1": timedelta(days=1),
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        model_name: Optional[str] = None,
        tokenizer_name: Optional[str] = None,
        device: Optional[str] = None,
        max_context: int = 512,
        lookback: int = 400,
        pred_len: int = 120,
    ):
        self.model_name = model_name or "NeoQuasar/Kronos-small"
        self.tokenizer_name = tokenizer_name or "NeoQuasar/Kronos-Tokenizer-base"
        self.device = device or "cpu"
        self.max_context = max_context
        self.lookback = lookback
        self.pred_len = pred_len

        self.tokenizer: Optional[KronosTokenizer] = None
        self.model: Optional[Kronos] = None
        self.predictor: Optional[KronosPredictor] = None
        self.is_loaded: bool = False

        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "kronos" in cfg:
                        kcfg = cfg["kronos"]
                        self.model_name = kcfg.get("model_name", self.model_name)
                        self.tokenizer_name = kcfg.get("tokenizer_name", self.tokenizer_name)
                        self.device = kcfg.get("device", self.device)
                        self.max_context = kcfg.get("max_context", self.max_context)
                        self.lookback = kcfg.get("lookback", self.lookback)
                        self.pred_len = kcfg.get("pred_len", self.pred_len)
            except Exception as e:
                logger.error(f"Failed to parse Kronos config from {config_path}: {e}")

    def load_model(self) -> Tuple[bool, str]:
        """
        Loads Kronos model and tokenizer from Hugging Face Hub / local cache onto requested device.
        """
        try:
            logger.info(f"Loading Kronos tokenizer '{self.tokenizer_name}'...")
            self.tokenizer = KronosTokenizer.from_pretrained(self.tokenizer_name)

            logger.info(f"Loading Kronos model '{self.model_name}'...")
            self.model = Kronos.from_pretrained(self.model_name)

            # Resolve device support safely
            target_device = self.device.lower()
            if target_device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but unavailable. Falling back to CPU.")
                target_device = "cpu"
            elif target_device == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
                logger.warning("MPS requested but unavailable. Falling back to CPU.")
                target_device = "cpu"

            self.tokenizer.eval()
            self.model.eval()

            self.predictor = KronosPredictor(
                model=self.model,
                tokenizer=self.tokenizer,
                device=target_device,
                max_context=self.max_context,
            )
            self.is_loaded = True
            msg = f"Successfully loaded Kronos model '{self.model_name}' on device '{target_device}'."
            logger.info(msg)
            return True, msg

        except Exception as e:
            msg = f"Failed to load Kronos model/tokenizer: {str(e)}"
            logger.error(msg)
            self.is_loaded = False
            return False, msg

    def predict_forecast(
        self,
        df: pd.DataFrame,
        symbol: str = "EURUSD",
        timeframe: str = "M5",
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 0.9,
        sample_count: int = 1,
    ) -> Tuple[Optional[PredictionResult], Optional[str]]:
        """
        Consumes validated closed-candle DataFrame and produces a structured PredictionResult.
        """
        if not self.is_loaded or self.predictor is None:
            ok, msg = self.load_model()
            if not ok:
                return None, msg

        if df is None or not isinstance(df, pd.DataFrame) or len(df) == 0:
            return None, "Input DataFrame is empty or None."

        # Validate required columns
        req_cols = ["open", "high", "low", "close", "timestamps"]
        for col in req_cols:
            if col not in df.columns:
                return None, f"Missing required column in input DataFrame: {col}"

        # Enforce lookback history requirement
        if len(df) < self.lookback:
            return None, f"Insufficient closed candles: expected at least {self.lookback}, got {len(df)}."

        # Extract last `lookback` closed candles to prevent look-ahead
        context_df = df.iloc[-self.lookback:].copy().reset_index(drop=True)

        # Prepare volume / amount channels without altering values
        if "volume" not in context_df.columns:
            context_df["volume"] = 0.0
        if "amount" not in context_df.columns:
            context_df["amount"] = context_df["volume"] * context_df[["open", "high", "low", "close"]].mean(axis=1)

        x_df = context_df[["open", "high", "low", "close", "volume", "amount"]]
        x_timestamp = pd.to_datetime(context_df["timestamps"]).reset_index(drop=True)

        # Generate future prediction timestamps
        last_ts = x_timestamp.iloc[-1]
        tf_delta = self.TIMEFRAME_DELTAS.get(timeframe.upper(), timedelta(minutes=5))
        future_timestamps = pd.Series([last_ts + tf_delta * (i + 1) for i in range(self.pred_len)])

        start_time = time.time()
        try:
            with torch.no_grad():
                pred_df = self.predictor.predict(
                    df=x_df,
                    x_timestamp=x_timestamp,
                    y_timestamp=future_timestamps,
                    pred_len=self.pred_len,
                    T=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    sample_count=sample_count,
                    verbose=False,
                )
            latency_sec = time.time() - start_time

        except Exception as e:
            msg = f"KronosPredictor inference failed: {str(e)}"
            logger.error(msg)
            return None, msg

        # Validate prediction DataFrame
        if pred_df is None or len(pred_df) != self.pred_len:
            return None, f"Predictor returned invalid prediction count: expected {self.pred_len}, got {len(pred_df) if pred_df is not None else 0}"

        if pred_df[["open", "high", "low", "close"]].isnull().sum().sum() > 0:
            return None, "Predictor output contains NaN values."

        pred_res = PredictionResult(
            symbol=symbol,
            timestamp=datetime.now(),
            pred_len=self.pred_len,
            predicted_close=pred_df["close"].tolist(),
            predicted_open=pred_df["open"].tolist(),
            predicted_high=pred_df["high"].tolist(),
            predicted_low=pred_df["low"].tolist(),
            predicted_volume=pred_df["volume"].tolist(),
            metadata={
                "timeframe": timeframe,
                "model_name": self.model_name,
                "tokenizer_name": self.tokenizer_name,
                "lookback": self.lookback,
                "latency_sec": latency_sec,
                "forecast_start_ts": str(future_timestamps.iloc[0]),
                "forecast_end_ts": str(future_timestamps.iloc[-1]),
                "sample_count": sample_count,
                "temperature": temperature,
            },
        )

        logger.info(f"Generated {self.pred_len}-step forecast for {symbol} ({timeframe}) in {latency_sec:.2f}s.")
        return pred_res, None
