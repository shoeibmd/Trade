# Phase 4 — Astraea Forecasting Engine / Kronos Adapter Report

**Date**: October 6, 2026
**Product**: **Astraea MT5 — AI-Powered Forex Trading Intelligence**
**Execution Context**: Linux x86_64 | PyTorch 2.14.1+cu130 | Python 3.12.13

---

## 1. Executive Summary

Phase 4 implements the **Astraea Forecasting Adapter** (`trading/kronos_adapter.py`), which interfaces Astraea MT5 with the existing underlying foundation model (`Kronos`, `KronosTokenizer`, and `KronosPredictor`).

The adapter consumes validated 400 closed M5 candle DataFrames produced by the Market Data Engine (`trading/mt5_data.py`), extends time steps into the future by `pred_len=120` intervals, runs autoregressive foundation inference, and returns a structured `PredictionResult` (`trading/models.py`).

Core neural network files (`model/kronos.py`, `model/module.py`, `model/__init__.py`) remain 100% untouched.

---

## 2. Architecture & Integration Flow

```
┌────────────────────────────────────────────────────────┐
│                   MetaTrader 5 Terminal                 │
└───────────────────────────┬────────────────────────────┘
                            │ (M5 Closed Rates)
                            ▼
┌────────────────────────────────────────────────────────┐
│              trading.mt5_data.MT5DataEngine            │
│  - Retrieves 400 closed M5 candles (pos=1)            │
│  - Validates OHLC integrity, count, and monotonicity   │
└───────────────────────────┬────────────────────────────┘
                            │ (Validated Bar DataFrame)
                            ▼
┌────────────────────────────────────────────────────────┐
│           trading.kronos_adapter.KronosAdapter         │
│ 1. Validates input schema & lookback count (>= 400)    │
│ 2. Extends timestamps by pred_len=120 M5 steps         │
│ 3. Delegates to untouched KronosPredictor              │
└───────────────────────────┬────────────────────────────┘
                            │ (Autoregressive Rollout)
                            ▼
┌────────────────────────────────────────────────────────┐
│           UNTOUCHED Kronos Foundation Model            │
│  - KronosTokenizer (BSQuantizer)                       │
│  - Kronos (Hierarchical Transformer)                   │
│  - KronosPredictor (model/kronos.py)                   │
└───────────────────────────┬────────────────────────────┘
                            │ (Predicted OHLCV Data)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 trading.models.PredictionResult        │
│  - symbol: "EURUSD"                                    │
│  - pred_len: 120                                       │
│  - predicted_close, predicted_open, predicted_high,   │
│    predicted_low, predicted_volume                     │
│  - metadata: timeframe, latency_sec, model_name, etc.  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Preprocessing & Volume / Amount Handling

- **Input Contract**: Consumes `open`, `high`, `low`, `close`, `volume`, `amount`, and `timestamps`.
- **Lookback Requirement**: Requires at least `lookback=400` closed candles.
- **Volume / Amount Representation**:
  - Forex brokers provide **Tick Volume** (quote updates per bar).
  - MT5 `tick_volume` is mapped to `volume`.
  - `amount` is mapped to `real_volume` when provided by the broker, or computed as `volume * mean_price` to fulfill `KronosPredictor` schema requirements without altering financial meaning or model preprocessing logic.

---

## 4. Configuration & Model Loading

Non-secret configuration defined in `config/config.yaml`:

```yaml
kronos:
  model_name: NeoQuasar/Kronos-small
  tokenizer_name: NeoQuasar/Kronos-Tokenizer-base
  max_context: 512
  lookback: 400
  pred_len: 120
  device: cpu
```

- **Device Handling**: Supports `cpu`, `cuda`, and `mps`. If `cuda` or `mps` is requested on an unsupported platform, the adapter logs a warning and safely falls back to `cpu`.
- **Model / Tokenizer Weights**: Loaded dynamically via Hugging Face Hub (`NeoQuasar/Kronos-small` and `NeoQuasar/Kronos-Tokenizer-base`).

---

## 5. Real Kronos Model Inference Benchmark

An actual, un-mocked inference benchmark was executed during automated testing using pre-trained `Kronos-small` and `Kronos-Tokenizer-base`:

```text
Real Model Inference Benchmark:
--------------------------------
Model: NeoQuasar/Kronos-small
Tokenizer: NeoQuasar/Kronos-Tokenizer-base
Device: CPU
Input Context: 400 closed M5 EURUSD candles
Forecast Horizon: 120 steps
Inference Latency: 22.41 seconds
Output Shape: 120 OHLCV predicted steps
NaN Count: 0
OHLC Relationship Check: PASSED (High >= Low for all 120 predicted steps)
Status: SUCCESS
```

---

## 6. Test Results

**Execution Command**:
```bash
python /tmp/run_all_tests.py
```

**Exact Pytest Output**:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0 -- /home/jules/.pyenv/versions/3.12.13/bin/python
cachedir: .pytest_cache
rootdir: /app
collecting ... collected 26 items

tests/test_foundation.py::test_required_directories_exist PASSED         [  3%]
tests/test_foundation.py::test_configuration_file_loads PASSED           [  7%]
tests/test_foundation.py::test_env_example_file_exists PASSED            [ 11%]
tests/test_foundation.py::test_kronos_imports_remain_functional PASSED   [ 15%]
tests/test_foundation.py::test_trading_models_instantiation PASSED       [ 19%]
tests/test_mt5_connection.py::test_mt5_connection_initial_state PASSED   [ 23%]
tests/test_mt5_connection.py::test_mt5_connection_env_vars PASSED        [ 26%]
tests/test_mt5_connection.py::test_mt5_connection_missing_package_graceful_handling PASSED [ 30%]
tests/test_mt5_connection.py::test_mt5_connection_mocked_success PASSED  [ 34%]
tests/test_mt5_data.py::test_validation_successful PASSED                [ 38%]
tests/test_mt5_data.py::test_validation_insufficient_count PASSED        [ 42%]
tests/test_mt5_data.py::test_validation_malformed_ohlc PASSED            [ 46%]
tests/test_mt5_data.py::test_validation_duplicate_timestamps PASSED      [ 50%]
tests/test_mt5_data.py::test_validation_unordered_timestamps PASSED      [ 53%]
tests/test_mt5_data.py::test_get_closed_bars_mocked_success_and_forming_bar_exclusion PASSED [ 57%]
tests/test_mt5_data.py::test_get_closed_bars_empty_response PASSED       [ 61%]
tests/test_mt5_data.py::test_get_closed_bars_missing_mt5_package PASSED  [ 65%]
tests/test_kronos_adapter.py::test_adapter_initialization_defaults PASSED [ 69%]
tests/test_kronos_adapter.py::test_adapter_insufficient_candles_rejection PASSED [ 73%]
tests/test_kronos_adapter.py::test_adapter_missing_required_column_rejection PASSED [ 76%]
tests/test_kronos_adapter.py::test_adapter_mocked_prediction_success PASSED [ 80%]
tests/test_kronos_adapter.py::test_real_kronos_model_inference PASSED    [ 84%]
tests/test_kronos_regression.py::test_kronos_predictor_regression[512] PASSED [ 88%]
tests/test_kronos_regression.py::test_kronos_predictor_regression[256] PASSED [ 92%]
tests/test_kronos_regression.py::test_kronos_predictor_mse[512-0.008979] PASSED [ 96%]
tests/test_kronos_regression.py::test_kronos_predictor_mse[256-0.003741] PASSED [100%]

======================== 26 passed, 1 warning in 71.49s ========================
```

- **Total Test Count**: 26
- **Passed**: 26
- **Failed**: 0
- **Duration**: 71.49s

---

## 7. Safety & Core Model Protection Confirmations

- **Signal Engine Implemented**: NO
- **Risk Engine Implemented**: NO
- **Orders Placed**: NONE
- **Positions Opened**: NONE
- **Trading Execution Implemented**: NO
- **Live Trading Enabled**: DISABLED (`live_trading_enabled: false`)
- **Core Model Files**:
  - `model/kronos.py`: **UNCHANGED**
  - `model/module.py`: **UNCHANGED**
  - `model/__init__.py`: **UNCHANGED**

---

## 8. Final Status Assessment

```text
PHASE 4 STATUS:
COMPLETE

KRONOS ADAPTER:
COMPLETE

MODEL LOADING:
PASSED

TOKENIZER LOADING:
PASSED

REAL MODEL INFERENCE:
PASSED

FORECAST OUTPUT VALIDATION:
PASSED

TESTS:
26 PASSED / 0 FAILED

ORIGINAL KRONOS REGRESSION:
4 PASSED / 0 FAILED

CORE MODEL:
UNCHANGED

SIGNAL ENGINE:
NOT IMPLEMENTED

RISK ENGINE:
NOT IMPLEMENTED

TRADE EXECUTION:
NOT IMPLEMENTED

ORDERS PLACED:
NO

LIVE TRADING:
DISABLED

READY FOR PHASE 5:
YES
```
