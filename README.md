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

<img src="./assets/branding/astraea_logo.png" width="120" alt="Astraea MT5 Logo">

</p>

> **Astraea MT5** is an enterprise-grade AI-powered MetaTrader 5 (MT5) Forex trading intelligence platform.
> It integrates real-time MT5 tick and bar streaming data, technical indicators, probabilistic signal generation, risk management, and execution engines.

---

### 📌 Model & Foundation Architecture Notice

> **Note**: **Astraea MT5** is the trading application and execution framework. It uses the existing **Kronos** foundation forecasting model (`Kronos`, `KronosTokenizer`, `KronosPredictor`) as its core time-series forecasting component. Original Kronos model architecture, tokenization, weights, citations, and licenses remain intact.

---

## 🚀 Overview & Features

Astraea MT5 provides a complete 5-layer trading architecture built for high-precision Forex forecasting and systematic paper execution:

1. **Layer 1: MT5 Data Infrastructure Layer** (`MT5DataEngine`, `DataValidator`)
   - Real-time rate collection, candle aggregation, and missing bar cleaning.
2. **Layer 2: AI Foundation Model Layer** (`KronosForexAdapter`, `KronosPredictor`, `KronosTokenizer`)
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

Then open your browser at `http://localhost:5000`.

---

## 📈 Making Forecasts using the Kronos Foundation Model

Forecasting in Astraea MT5 leverages the underlying `KronosPredictor` class.

```python
from model import Kronos, KronosTokenizer, KronosPredictor

# Load foundation model and tokenizer
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
model = Kronos.from_pretrained("NeoQuasar/Kronos-small")

# Initialize predictor
predictor = KronosPredictor(model, tokenizer, max_context=512)
```

---

## 📖 Upstream Model Citation & Acknowledgments

The core forecasting engine in Astraea MT5 relies on the Kronos foundation model research:

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
