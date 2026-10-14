<div align="center">
  <h2><b>Astraea MT5 — AI-Powered Forex Trading Intelligence</b></h2>
</div>

<div align="center">

<a href="./LICENSE">
<img src="https://img.shields.io/github/license/shiyu-coder/Kronos?color=green" alt="License">
</a>
<img src="https://img.shields.io/badge/System-PAPER-gold" alt="Mode">
<img src="https://img.shields.io/badge/Live_Trading-Disabled-red" alt="Live Trading">

</div>

<p align="center">

<img src="./assets/branding/logo.svg" width="380" alt="Astraea MT5 Logo">

</p>

> **Astraea MT5** is an enterprise-grade AI-powered MetaTrader 5 (MT5) Forex trading intelligence platform.
> Astraea MT5 uses its integrated forecasting engine to generate market forecasts.

---

### 📌 Architecture & Model Attribution Notice

> **Note**: **Astraea MT5** is the trading application and execution framework. It integrates the underlying foundation forecasting model as its time-series forecasting component. Upstream research citations, model weights, and licenses remain preserved.

---

## 🚀 Overview & Features

Astraea MT5 provides a complete 5-layer trading architecture built for high-precision Forex forecasting and systematic paper execution:

1. **Layer 1: MT5 Data Infrastructure Layer** (`MT5DataEngine`, `DataValidator`)
   - Real-time rate collection, candle aggregation, and missing bar cleaning.
2. **Layer 2: AI Foundation Forecasting Engine Layer** (`AstraeaForecastingEngine`, `KronosAdapter`)
   - Pretrained autoregressive foundation model for OHLCV K-line sequences.
3. **Layer 3: Strategy & Intelligence Layer** (`IndicatorEngine`, `ForexSignalEngine`)
   - Directional forecasts combined with ATR, RSI, EMA, and Bollinger Band filters.
4. **Layer 4: Risk & Execution Engine Layer** (`ForexRiskManager`, `PaperExecutionEngine`, `PositionManager`)
   - Dynamic lot sizing based on account balance, pip value, and stop-loss distance with safety controls (`system.mode: PAPER`, `live_trading_enabled: false`).
5. **Layer 5: Analytics & Monitoring Dashboard** (`WebUI`)
   - Interactive Flask/Plotly web dashboard for monitoring forecasts, positions, and backtest results.

---

## 📦 Getting Started

### Installation

1. Ensure Python 3.10+ is installed, then install requirements:

```shell
pip install -r requirements.txt
```

### 📊 Launching the Web UI Dashboard

To launch the Astraea MT5 Web UI Dashboard:

```shell
python webui/app.py
```

Then open your browser at `http://localhost:7070` (or `http://localhost:5000` if configured).

---

## 📈 Making Forecasts Using the Astraea MT5 Forecasting Engine

Generating forecasts in Astraea MT5 is straightforward using the high-level `AstraeaForecastingEngine` class.

```python
import pandas as pd
from trading import AstraeaForecastingEngine

# Initialize the Astraea MT5 Forecasting Engine
engine = AstraeaForecastingEngine(
    model_name="NeoQuasar/Kronos-small",
    device="cpu",
    lookback=400,
    pred_len=120
)

# Load model weights
engine.load()

# Prepare historical closed candles DataFrame
# df must contain columns ['open', 'high', 'low', 'close', 'timestamps']
df = pd.read_csv("./data/XSHG_5min_600977.csv")
df['timestamps'] = pd.to_datetime(df['timestamps'])

# Generate market forecast
prediction, error = engine.forecast(
    df=df,
    symbol="EURUSD",
    timeframe="M5",
    temperature=1.0
)

if prediction:
    print(f"Generated {prediction.pred_len}-step forecast for {prediction.symbol}")
    print("Predicted Close Prices:", prediction.predicted_close[:5])
```

---

## 📖 Upstream Model Citation & Acknowledgments

The core foundation forecasting research integrated in Astraea MT5 is cited below:

```bibtex
@misc{shi2025kronos,
      title={Kronos: A Foundation Model for the Language of Financial Markets},
      author={Yu Shi and Zongliang Fu and Shuo Chen and Bohan Zhao and Wei Xu and Changshui Zhang and Jian Li},
      year={2025},
      eprint={2508.02739},
      archivePrefix={arXiv},
      primaryClass={q-fin.ST},
      url={https://arxiv.org/abs/2508.02739},
}
```

## 📜 License
This project is licensed under the [MIT License](./LICENSE).
