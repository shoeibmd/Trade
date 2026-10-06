# Astraea MT5

### AI-Powered Forex Trading Intelligence

Astraea MT5 is an AI-assisted Forex analysis and automated trading platform integrated with MetaTrader 5 (MT5). It leverages foundation AI model forecasting to analyze market K-lines, generate trading signals, manage risk, and execute trades on MetaTrader 5.

---

## 🚀 Product Overview

Astraea MT5 provides institutional-grade trading intelligence for foreign exchange (Forex) markets:
- **AI-Driven Forecasting**: Employs discrete tokenized autoregressive Transformer models to predict future price movements over custom lookback windows (M1, M5, H1, D1).
- **MetaTrader 5 Integration**: Automated market data pipeline and execution bridge for MT5.
- **Risk & Capital Preservation**: Rules-based risk management engine enforcing drawdown limits, max position limits, and automatic stop-loss/take-profit calculations.
- **Web Visualization Dashboard**: Real-time interactive charts, trade signals, and account monitoring.

---

## 🏛️ System Architecture

```mermaid
graph TD
    MT5[MetaTrader 5 Terminal] -->|Live Rates / History| DataEngine[Astraea Market Data Engine]
    DataEngine --> DataVal[Data Validation & Cleaning]
    DataVal --> ForexAdapter[Astraea Forex Adapter]
    ForexAdapter --> ForecastEngine[Astraea Forecasting Engine<br/>(Kronos Foundation Model)]
    ForecastEngine --> TechAnalysis[Technical Analysis Module]
    TechAnalysis --> SignalEngine[Astraea Signal Engine]
    SignalEngine --> RiskEngine[Astraea Risk Engine]
    RiskEngine --> TradeDecision[Trade Decision Matrix]
    TradeDecision --> ExecutionEngine[Astraea Execution Engine]
    ExecutionEngine -->|Orders / Modifies| MT5
    ExecutionEngine --> PosManager[Position Management]
    PosManager --> DB[(Database / Log Storage)]
    DB --> Dashboard[Astraea Web Dashboard]
```

---

## 📦 Project Structure

```
Astraea MT5/
├── assets/branding/             # Official logo SVGs, favicons, and Brand Guidelines
├── config/                      # System configuration (config.yaml, .env.example)
├── model/                       # Core AI Forecasting Engine (Kronos Foundation Model)
│   ├── kronos.py                # KronosTokenizer, Kronos, KronosPredictor
│   └── module.py                # BSQuantizer and Attention Transformer blocks
├── trading/                     # Astraea Application & Trading Schemas
│   └── models.py                # TickData, BarData, PredictionResult, TradingSignal, Position
├── examples/                    # Prediction and backtesting examples
├── finetune/                    # Qlib fine-tuning pipeline
├── finetune_csv/                # Generic CSV fine-tuning pipeline
├── tests/                       # Regression & Foundation Unit Tests
│   ├── test_foundation.py       # Astraea MT5 foundation tests
│   └── test_kronos_regression.py # Forecasting engine regression tests
└── webui/                       # Astraea MT5 Web Visualization Dashboard
```

---

## ⚙️ Quick Start

### 1. Installation

Install Python 3.10+ and dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your MetaTrader 5 account details:

```bash
cp .env.example .env
```

Review system settings in `config/config.yaml`:

```yaml
system:
  mode: PAPER
  log_level: INFO

mt5:
  symbols:
    - EURUSD
  timeframe: M5

kronos:
  model_name: NeoQuasar/Kronos-small
  tokenizer_name: NeoQuasar/Kronos-Tokenizer-base
  max_context: 512
  lookback: 400
  pred_len: 120
  device: cpu

strategy:
  minimum_signal_score: 70

risk:
  risk_per_trade_percent: 1.0
  max_open_positions: 1
  max_daily_loss_percent: 3.0
  max_consecutive_losses: 3

safety:
  live_trading_enabled: false
```

### 3. Launching Web Dashboard

Run the Astraea MT5 Web Dashboard:

```bash
python webui/app.py
```

Access the dashboard at `http://localhost:7070`.

---

## 🧪 Testing

Run the test suite:

```bash
python -m pytest tests/
```

**Test Verification Status**:
- Foundation Tests (`tests/test_foundation.py`): **PASSED** (5/5)
- Regression Tests (`tests/test_kronos_regression.py`): **PASSED** (4/4)
- Total Pass Rate: **100% (9/9 passed)**

---

## 📜 Technology Attribution & Licensing

Astraea MT5 is built using the open-source **Kronos** time series foundation model (`NeoQuasar/Kronos`) as its underlying technical forecasting engine. Core neural network modules (`model/kronos.py`, `model/module.py`) retain original technical identifiers for complete compatibility.

Licensed under the [MIT License](./LICENSE).
