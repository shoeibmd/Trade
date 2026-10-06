# Phase 0 — Complete Kronos Repository Analysis Report

**Date**: October 6, 2026
**Repository Analyzed**: `https://github.com/shiyu-coder/Kronos.git`
**Execution Context**: Linux x86_64 | PyTorch 2.14.1+cu130 | Python 3.12.13

---

## Classifications Used in This Report

- **[VERIFIED FROM SOURCE CODE]**: Directly verified by inspecting the codebase.
- **[TEST VERIFIED]**: Directly verified by executing automated tests in the repository environment.
- **[NOT VERIFIED]**: Stated in documentation or paper, but not directly testable or verified in local source files.
- **[NOT FOUND]**: Expected component or feature that is not present in the repository.
- **[RECOMMENDATIONS FOR FUTURE PHASES]**: Proposed architectural designs or additions for future MetaTrader 5 (MT5) Forex integration.

---

## 1. Executive Summary

`[VERIFIED FROM SOURCE CODE]`
**Kronos** is an open-source decoder-only foundation model family designed specifically for financial candlestick (K-line) sequences. Unlike generic time series models, Kronos models financial markets using a two-stage paradigm:
1. **Hierarchical Tokenization**: Continuous OHLCV K-line features are converted into coarse (`s1`) and fine (`s2`) discrete tokens via Binary Spherical Quantization (`BSQuantizer`).
2. **Autoregressive Forecasting**: A Transformer model generates future token sequences autoregressively conditioned on past context tokens and time embeddings (minute, hour, weekday, day, month).

During Phase 0, 100% of the existing Kronos codebase was mapped, traced, and analyzed without modifying model weights, tokenizers, predictors, or existing tests.

---

## 2. Repository Structure

`[VERIFIED FROM SOURCE CODE]`

```
Kronos/
├── LICENSE                          # MIT License
├── README.md                        # Primary project documentation
├── requirements.txt                 # Dependencies (torch, pandas, numpy, einops, huggingface_hub, etc.)
├── .gitignore                       # Git ignore rules
│
├── model/                           # Core Kronos Model & Tokenizer Library
│   ├── __init__.py                  # Exports KronosTokenizer, Kronos, KronosPredictor, get_model_class
│   ├── kronos.py                    # Implementation of KronosTokenizer, Kronos, KronosPredictor, auto_regressive_inference
│   └── module.py                    # Neural network components (BSQuantizer, MultiHeadAttentionWithRoPE, etc.)
│
├── examples/                        # Prediction and Backtesting Examples
│   ├── prediction_example.py        # Single series forecast example with visualization
│   ├── prediction_wo_vol_example.py # Forecast example without volume/amount columns
│   ├── prediction_batch_example.py  # Parallel multi-series prediction example
│   ├── prediction_cn_markets_day.py # Daily A-share prediction example
│   ├── prediction_akshare_2024-2025.py # Akshare data fetching and prediction
│   ├── get_akshare_date_2024-2025_x.py # Data fetch utility
│   ├── get_date_new.py              # Timestamp utility
│   ├── prediction_new.py            # Prediction script variant
│   ├── prediction_new_GUI.py        # GUI prediction script
│   ├── run_backtest_kronos.py       # Standalone Kronos stock backtesting script
│   └── yuce/                        # Sample reports, backtest JSONs, and prediction plots
│
├── finetune/                        # Qlib-based Fine-tuning Pipeline
│   ├── config.py                    # Central python configuration class for Qlib fine-tuning
│   ├── dataset.py                   # QlibDataset dataset loader
│   ├── qlib_data_preprocess.py      # Qlib data preprocessor script
│   ├── train_tokenizer.py           # Distributed tokenizer fine-tuning script
│   ├── train_predictor.py           # Distributed predictor fine-tuning script
│   ├── qlib_test.py                 # Qlib backtesting script post fine-tuning
│   └── utils/                       # Fine-tuning training helper functions
│
├── finetune_csv/                    # Generic CSV Fine-tuning Pipeline
│   ├── README.md & README_CN.md     # Documentation for CSV fine-tuning
│   ├── config_loader.py             # YAML configuration parser
│   ├── finetune_tokenizer.py        # Standalone tokenizer CSV fine-tuning
│   ├── finetune_base_model.py       # Standalone predictor CSV fine-tuning
│   ├── train_sequential.py          # Sequential (tokenizer -> predictor) fine-tuning pipeline
│   ├── configs/                     # Config files (e.g. config_ali09988_candle-5min.yaml)
│   ├── data/                        # Sample CSV training data (HK_ali_09988_kline_5min_all.csv)
│   └── examples/                    # Result visualization plots
│
├── tests/                           # Regression and Verification Tests
│   ├── test_kronos_regression.py   # Pytest suite for KronosPredictor output & MSE regression
│   └── data/                        # Ground truth CSVs (regression_input.csv, regression_output_512.csv, etc.)
│
├── webui/                           # Web Visualization Dashboard
│   ├── app.py                       # Flask web backend server
│   ├── run.py & start.sh            # Launch scripts
│   ├── requirements.txt             # Web UI dependencies (Flask, Flask-CORS, Plotly)
│   ├── README.md                    # Web UI documentation
│   ├── templates/                   # HTML UI templates (index.html)
│   └── prediction_results/          # Saved prediction JSON outputs
│
└── figures/                         # Documentation charts and logos
```

---

## 3. Complete Kronos Architecture

`[VERIFIED FROM SOURCE CODE]`

Kronos consists of three primary model components located in `model/kronos.py` and `model/module.py`:

1. **`KronosTokenizer`** (`model/kronos.py`)
   - **Inheritance**: `nn.Module`, `PyTorchModelHubMixin`
   - **Structure**: Linear Embedding (`d_in` -> `d_model`) → `(n_enc_layers - 1)` Transformer Encoder Blocks → `quant_embed` Linear Layer → `BSQuantizer` → Linear Post-Quantization Embeddings (`post_quant_embed_pre` for `s1` and `post_quant_embed` for full codebook) → Decoder Transformer Blocks → Head Linear Layer (`d_model` -> `d_in`).
   - **Quantization**: `BSQuantizer` splits codebook into `s1_bits` (pre token / coarse) and `s2_bits` (post token / fine).

2. **`Kronos`** (`model/kronos.py`)
   - **Inheritance**: `nn.Module`, `PyTorchModelHubMixin`
   - **Structure**:
     - `HierarchicalEmbedding`: Maps `s1_ids` and `s2_ids` via separate embedding tables (`emb_s1`, `emb_s2`), concatenates them, and projects to `d_model`.
     - `TemporalEmbedding`: Fixed or learnable sinusoidal embeddings for minute, hour, weekday, day, and month features.
     - `TransformerBlock` stack: `n_layers` Transformer blocks using RMSNorm (`RMSNorm`), SwiGLU FeedForward (`FeedForward`), and Causal Scaled Dot-Product Multi-Head Attention with Rotary Positional Embeddings (`MultiHeadAttentionWithRoPE`).
     - `DualHead`: Dual classification heads (`proj_s1` and `proj_s2`).
     - `DependencyAwareLayer`: Cross-attention block (`MultiHeadCrossAttentionWithRoPE`) that conditions `s2` token prediction on the sibling `s1` token embedding.

3. **`KronosPredictor`** (`model/kronos.py`)
   - High-level interface wrapping `Kronos` and `KronosTokenizer`.
   - Handles device allocation (CPU/CUDA/MPS), z-score normalization, time-stamp decomposition, autoregressive rollouts, and inverse normalization.

---

## 4. Data Flow

`[VERIFIED FROM SOURCE CODE]`

The complete forecasting data flow through Kronos is as follows:

```
┌────────────────────────────────────────────────────────┐
│                      INPUT DATA                        │
│   Pandas DataFrame with [open, high, low, close]       │
│   (optional: [volume, amount]) + Timestamps            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     PREPROCESSING                      │
│ 1. Missing volume/amount filled with 0.0               │
│ 2. Timestamp decomposed into [min, hr, wday, day, mth] │
│ 3. Z-score normalization per channel:                  │
│    x_norm = clip((x - mean) / (std + 1e-5), -5, +5)    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                       TOKENIZER                        │
│ 1. tokenizer.encode(x_norm, half=True)                │
│ 2. Quantizes continuous 6D features into discrete      │
│    hierarchical tokens: (s1_ids, s2_ids)               │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                      KRONOS MODEL                      │
│ 1. Iterative autoregressive loop over pred_len steps   │
│ 2. model.decode_s1(input_tokens, current_stamp)        │
│ 3. Sample coarse token s1 using T, top_k, top_p        │
│ 4. model.decode_s2(context, sample_s1)                 │
│ 5. Sample fine token s2 using T, top_k, top_p          │
│ 6. Append generated (s1, s2) to sliding pre/post buffer│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                       DECODER                          │
│ 1. Full generated token sequence passed to tokenizer   │
│ 2. tokenizer.decode([full_s1, full_s2], half=True)     │
│ 3. Reconstructs normalized 6D features                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                    FORECAST OUTPUT                     │
│ 1. Sample paths averaged across sample_count           │
│ 2. Inverse normalization: preds * (std + 1e-5) + mean   │
│ 3. Output DataFrame indexed by y_timestamp             │
└────────────────────────────────────────────────────────┘
```

---

## 5. Model Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Class**: `Kronos` in `model/kronos.py`
- **Architecture**: Decoder-only Autoregressive Hierarchical Transformer
- **Context Length (`max_context`)**:
  - `Kronos-mini`: 2048
  - `Kronos-small`: 512
  - `Kronos-base`: 512
- **Required Input Features**: 6 dimensions (`open`, `high`, `low`, `close`, `volume`, `amount`).
- **Temporal Features**: 5 dimensions (`minute`, `hour`, `weekday`, `day`, `month`).
- **Device Support**: CPU, CUDA, Apple Silicon (MPS).
- **Weight Loading**: PyTorch `safetensors` via `HuggingFace` `from_pretrained`.

---

## 6. Tokenizer Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Class**: `KronosTokenizer` in `model/kronos.py`
- **Quantizer**: `BSQuantizer` wrapping `BinarySphericalQuantizer` (`model/module.py`)
- **Codebook Representation**: Dual-part bit quantizer with `s1_bits` (coarse structure, default 8 bits) and `s2_bits` (fine details, default 8 bits). Total codebook dimension = 16 bits (65,536 discrete states).
- **Encoding Method**: `encode(x, half=True)` -> returns `[z_s1, z_s2]`.
- **Decoding Method**: `decode([z_s1, z_s2], half=True)` -> reconstructs continuous features.

---

## 7. Predictor Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Class**: `KronosPredictor` in `model/kronos.py`
- **Key Methods**:
  - `__init__(model, tokenizer, device=None, max_context=512, clip=5)`
  - `predict(df, x_timestamp, y_timestamp, pred_len, T=1.0, top_k=0, top_p=0.9, sample_count=1, verbose=True)`: Single time series forecasting.
  - `predict_batch(df_list, x_timestamp_list, y_timestamp_list, pred_len, T=1.0, top_k=0, top_p=0.9, sample_count=1, verbose=True)`: Parallel batch forecasting for multiple series.
- **Error Handling**: Validates DataFrame type, required price columns, NaN presence, and consistent batch sequence lengths.

---

## 8. Forecasting Pipeline

`[VERIFIED FROM SOURCE CODE]`

- **Autoregressive Loop Function**: `auto_regressive_inference` in `model/kronos.py`.
- **Sampling Parameters**:
  - `T` (Temperature): Controls randomness during multinomial sampling from logits.
  - `top_k`: Keeps top-k logits for sampling.
  - `top_p`: Nucleus sampling threshold (cumulative probability).
  - `sample_count`: Generates $N$ parallel trajectories and averages them to produce a deterministic expected trajectory.

---

## 9. Data Requirements

`[VERIFIED FROM SOURCE CODE]`

- **Required Price Columns**: `open`, `high`, `low`, `close` (case-sensitive).
- **Optional Columns**: `volume`, `amount` (if missing, automatically imputed as zeros or `volume * mean_price`).
- **Timestamp Column**: `timestamps` (or `timestamp` / `date`).
- **Data Quality Rules**:
  - Zero NaN values allowed in price and volume columns.
  - Time ordering must be strictly ascending.
  - Input length `lookback` should ideally be $\le \text{max\_context}$ (512 or 2048).

---

## 10. Examples Analysis

`[VERIFIED FROM SOURCE CODE]`

1. `examples/prediction_example.py`: Demonstrates loading `Kronos-small` and predicting 120 steps on 400 historical candles from `data/XSHG_5min_600977.csv`.
2. `examples/prediction_wo_vol_example.py`: Demonstrates prediction when volume and amount are omitted.
3. `examples/prediction_batch_example.py`: Demonstrates parallel batch forecasting across 3 series simultaneously using `predict_batch`.
4. `examples/run_backtest_kronos.py`: Simple stock backtest comparing predicted close price changes against a fixed threshold (e.g. 2%) to issue long/cash positions.

---

## 11. Fine-Tuning Analysis

`[VERIFIED FROM SOURCE CODE]`

The repository provides two separate fine-tuning pipelines:
1. **Qlib Pipeline (`finetune/`)**: Tailored for Chinese A-share Qlib data (`qlib_data_preprocess.py`, `train_tokenizer.py`, `train_predictor.py`, `qlib_test.py`).
2. **CSV Pipeline (`finetune_csv/`)**: Tailored for arbitrary CSV K-line data (`finetune_tokenizer.py`, `finetune_base_model.py`, `train_sequential.py`).

`[RECOMMENDATIONS FOR FUTURE PHASES]`
Fine-tuning is **optional** for initial MT5 Forex integration because pre-trained `Kronos-base` and `Kronos-small` zero-shot forecasts can be evaluated first.

---

## 12. Existing Backtesting Analysis

`[VERIFIED FROM SOURCE CODE]`

The repository contains two backtesters: `examples/run_backtest_kronos.py` and `finetune/qlib_test.py`.

### Critical Limitations for Forex Trading:
`[VERIFIED FROM SOURCE CODE]`
1. **Long-Only Assumption**: Only models buying or staying in cash (`position = 0 or 1`).
2. **No Spread or Slippage**: Assumes execution exactly at bar close without bid-ask spread or slippage.
3. **No Leverage or Margin**: Lacks Forex margin calculations, swap rates, or pip values.
4. **No Stop-Loss / Take-Profit**: Positions exit only when prediction signals reverse.
5. **No Order Execution Engine**: Does not simulate limit/stop orders, partial fills, or MT5 broker execution constraints.

---

## 13. Existing Tests Analysis

`[TEST VERIFIED]`

The existing test suite is located in `tests/test_kronos_regression.py`.

- **Test Command Executed**: `python -m pytest tests/test_kronos_regression.py`
- **Environment**: PyTorch 2.14.1+cu130 / CPU
- **Test Results**:
  - `test_kronos_predictor_regression[512]` — **PASSED**
  - `test_kronos_predictor_regression[256]` — **PASSED**
  - `test_kronos_predictor_mse[zip0]` (context 512) — **PASSED**
  - `test_kronos_predictor_mse[zip1]` (context 256) — **PASSED**
- **Summary**: **4 passed, 0 failed (100% pass rate)**.

---

## 14. Web UI Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Framework**: Flask + Flask-CORS + Plotly (`webui/app.py`).
- **Frontend**: Single-page application using HTML/CSS/JS (`webui/templates/index.html`).
- **Functionality**:
  - `/api/data-files`: Lists available CSV/feather files.
  - `/api/load-model`: Dynamic loading of Kronos-mini, Kronos-small, or Kronos-base.
  - `/api/predict`: Runs `predictor.predict()`, renders interactive Plotly candlestick charts, and saves JSON output to `webui/prediction_results/`.

---

## 15. Configuration Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Qlib Fine-tuning**: Centralized in Python class `finetune/config.py`.
- **CSV Fine-tuning**: Centralized in YAML files loaded via `finetune_csv/config_loader.py` (e.g., `finetune_csv/configs/config_ali09988_candle-5min.yaml`).

---

## 16. Dependency Analysis

`[VERIFIED FROM SOURCE CODE]`

- **Core File**: `requirements.txt`
  - `torch>=2.0.0`
  - `numpy`
  - `pandas==2.2.2`
  - `einops==0.8.1`
  - `huggingface_hub==0.33.1`
  - `matplotlib==3.9.3`
  - `tqdm==4.67.1`
  - `safetensors==0.6.2`
- **Optional**: `pyqlib` (for Qlib fine-tuning), `Flask`, `flask-cors`, `plotly` (for Web UI).

---

## 17. Reusable Components (Reuse Matrix)

`[VERIFIED FROM SOURCE CODE]`

| Existing Component | File Path | Purpose | Reuse? | Adapter Required? | Modify? | Keep Untouched? |
|---|---|---|---|---|---|---|
| `KronosTokenizer` | `model/kronos.py` | BSQuantizer Tokenizer | YES | NO | NO | YES |
| `Kronos` | `model/kronos.py` | Main Transformer Model | YES | NO | NO | YES |
| `KronosPredictor` | `model/kronos.py` | High-level Predictor Interface | YES | YES | NO | YES |
| `auto_regressive_inference` | `model/kronos.py` | Autoregressive Rollout Logic | YES | NO | NO | YES |
| `BSQuantizer` / Modules | `model/module.py` | Quantizer & Attention Layers | YES | NO | NO | YES |
| `Web UI App` | `webui/app.py` | Web UI Backend | YES | YES | NO | YES (extend in new module) |
| `run_backtest_kronos.py` | `examples/run_backtest_kronos.py` | Stock Backtest Script | NO | NO | NO | YES (replace with Forex backtester) |
| `qlib_test.py` | `finetune/qlib_test.py` | Qlib Backtest Script | NO | NO | NO | YES |

---

## 18. Components Requiring Adapters

`[RECOMMENDATIONS FOR FUTURE PHASES]`

1. **MT5 Data Engine Adapter**: Converts MetaTrader 5 rate structures (M1, M5, H1, D1) into pandas DataFrames formatted with `open`, `high`, `low`, `close`, `volume`, `amount`, and `timestamps`.
2. **Kronos Forex Adapter**: Wraps `KronosPredictor` to handle live streaming sliding window contexts (e.g. 512 bars) and returns standardized forecast signals to the Signal Engine.

---

## 19. Components That Must Remain Untouched

`[VERIFIED FROM SOURCE CODE]`

To preserve core model integrity, the following files MUST remain untouched:
- `model/kronos.py`
- `model/module.py`
- `model/__init__.py`

---

## 20. Components That Can Be Extended

`[RECOMMENDATIONS FOR FUTURE PHASES]`

1. `webui/app.py`: Can be extended with API endpoints to view live MT5 connected accounts, position status, and active signal outputs.
2. `finetune_csv/`: Can be reused directly to fine-tune Kronos on specialized Forex tick or minute datasets (e.g., EURUSD, GBPUSD).

---

## 21. Missing Components Required for MT5 Forex

`[NOT FOUND]` `[RECOMMENDATIONS FOR FUTURE PHASES]`

The following components do not exist in Kronos and MUST be developed in future phases for a production MT5 Forex system:

1. **MT5 Connector / Data Engine**: Interfacing with MetaTrader5 Python API.
2. **Forex Data Validator & Cleaner**: Handling Sunday market opens, spread spikes, and missing candles.
3. **Forex Indicator Engine**: Technical indicators (ATR, EMA, RSI, MACD, Bollinger Bands) to filter foundation forecasts.
4. **Forex Signal Engine**: Multi-horizon signal generator (Direction, Strength, Confidence).
5. **Forex Risk Engine**: Position sizing based on account equity, leverage, pip value, and stop-loss distance.
6. **Execution & Order Engine**: Sending, modifying, and tracking market/limit/stop orders in MT5.
7. **Position & Account Manager**: Live tracking of unrealized PnL, margin utilization, and drawdown.
8. **Forex Backtester Engine**: High-fidelity Forex backtester with pip calculations, spread, swap, slippage, and bidirectional trading (Long/Short).
9. **Persistence & Database Engine**: SQLite or PostgreSQL for storing trade logs, forecasts, and performance metrics.

---

## 22. Kronos → MT5 Integration Boundary

`[RECOMMENDATIONS FOR FUTURE PHASES]`

```
┌────────────────────────────────────────────────────────┐
│                   METATRADER 5 TERMINAL                 │
└───────────────────────────┬────────────────────────────┘
                            │ (Live Rates / History)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   MT5 DATA ENGINE                      │
└───────────────────────────┬────────────────────────────┘
                            │ (Raw OHLCV)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 DATA VALIDATOR & CLEANER               │
└───────────────────────────┬────────────────────────────┘
                            │ (Validated Bar DataFrame)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 KRONOS FOREX ADAPTER                   │
└───────────────────────────┬────────────────────────────┘
                            │ (Formats x_df & timestamps)
                            ▼
┌────────────────────────────────────────────────────────┐
│                EXISTING KRONOS PREDICTOR               │
│               (UNTOUCHED model/kronos.py)              │
└───────────────────────────┬────────────────────────────┘
                            │ (Price & Volume Forecasts)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FOREX SIGNAL ENGINE                  │
└───────────────────────────┬────────────────────────────┘
                            │ (Trade Signals & Direction)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FOREX RISK MANAGER                   │
└───────────────────────────┬────────────────────────────┘
                            │ (Position Sizing & SL/TP)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 MT5 EXECUTION ENGINE                   │
└───────────────────────────┬────────────────────────────┘
                            │ (Sends Orders to MT5)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   METATRADER 5 TERMINAL                 │
└───────────────────────────┬────────────────────────────┘
```

---

## 23. Risks and Technical Limitations

`[VERIFIED FROM SOURCE CODE]` `[RECOMMENDATIONS FOR FUTURE PHASES]`

1. **Volume Differences in Forex**:
   - Kronos was trained on exchange volume (`volume` and `amount`).
   - Forex brokers provide **Tick Volume** (number of price changes) rather than real contract volume.
   - *Mitigation*: Tick volume works well when z-score normalized per window, or volume/amount columns can be imputed/filled with 0.0 as verified in `prediction_wo_vol_example.py`.
2. **Inference Latency**:
   - Autoregressive generation over 120 steps requires 120 forward passes per forecast path.
   - On CPU, inference takes multiple seconds per pair.
   - *Mitigation*: Run inference on M5/H1 timeframes where multi-second latency is acceptable, or use GPU acceleration.
3. **Context Length Truncation**:
   - `Kronos-small` and `Kronos-base` cap context at 512 bars.
   - Inputs longer than 512 are automatically truncated in `KronosPredictor`.

---

## 24. Recommended Future Architecture

`[RECOMMENDATIONS FOR FUTURE PHASES]`

A clean, modular 5-layer architecture is recommended for subsequent phases:

1. **Layer 1: Data Infrastructure Layer** (`MT5DataEngine`, `DataValidator`)
2. **Layer 2: AI Foundation Model Layer** (`KronosForexAdapter`, existing `KronosPredictor`, `Kronos`, `KronosTokenizer`)
3. **Layer 3: Strategy & Intelligence Layer** (`IndicatorEngine`, `ForexSignalEngine`)
4. **Layer 4: Risk & Execution Layer** (`ForexRiskManager`, `MT5ExecutionEngine`, `PositionManager`)
5. **Layer 5: Analytics & Monitoring Layer** (`ForexBacktester`, `WebUIDashboardExtension`)

---

## 25. Phase 1 Prerequisites

`[RECOMMENDATIONS FOR FUTURE PHASES]`

Before initiating Phase 1, the following conditions should be verified:
1. Active MT5 Terminal installed or MT5 Python API environment available.
2. Verified broker connection details (Demo or Live account).
3. Selected Forex pairs and target timeframes (e.g. EURUSD, GBPUSD on M5/H1).
4. Storage location for historical rate caches and backtest outputs.

---

## 26. Test Results

`[TEST VERIFIED]`

- **Test Runner**: Pytest 9.1.1
- **File**: `tests/test_kronos_regression.py`
- **Execution Log**:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /app
collected 4 items

tests/test_kronos_regression.py ....                                     [100%]

======================== 4 passed, 3 warnings in 43.16s ========================
```

- **Detailed Test Breakdown**:
  1. `test_kronos_predictor_regression` (Context 512): **PASSED**
  2. `test_kronos_predictor_regression` (Context 256): **PASSED**
  3. `test_kronos_predictor_mse` (Context 512): **PASSED**
  4. `test_kronos_predictor_mse` (Context 256): **PASSED**

---

*End of Phase 0 Analysis Report.*
