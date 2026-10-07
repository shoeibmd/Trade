# Phase 5 — Technical Indicator Engine Report

**Date**: October 6, 2026
**Product**: **Astraea MT5 — AI-Powered Forex Trading Intelligence**
**Execution Context**: Linux x86_64 | PyTorch 2.14.1+cu130 | Python 3.12.13

---

## 1. Executive Summary

Phase 5 implements the **Astraea Technical Indicator Engine** (`trading/indicators.py`), which computes trend (EMA), momentum (RSI), volatility (ATR), trend strength (ADX), and deterministic price/market structure on validated closed-candle market DataFrames.

The indicator engine operates strictly on completed closed-bar history with zero future data leakage or look-ahead bias, as proven by deterministic unit tests (`test_no_future_leakage_proof`).

Core neural network files (`model/kronos.py`, `model/module.py`, `model/__init__.py`) remain 100% untouched.

---

## 2. Files Created / Modified

- `trading/indicators.py` — **CREATED**: Implements `TechnicalIndicatorEngine`, `MarketStructure`, `StructureState` (EMA, RSI, ATR, ADX, Market Structure).
- `tests/test_indicators.py` — **CREATED**: Comprehensive unit test suite covering EMA, RSI, ATR, ADX, Market Structure, warm-up NaN preservation, 400 closed M5 bar integration, and explicit no-future-leakage proof.
- `config/config.yaml` — **MODIFIED**: Added configurable indicator parameters (`ema_fast`, `ema_slow`, `ema_trend`, `ema_baseline`, `rsi_period`, `adx_period`, `atr_period`, `swing_window`).
- `PHASE_5_INDICATOR_ENGINE_REPORT.md` — **CREATED**: Phase 5 report.

---

## 3. Indicator Engine Architecture

```
┌────────────────────────────────────────────────────────┐
│              trading.mt5_data.MT5DataEngine            │
│  - Retrieves & validates 400 closed M5 bars (pos=1)    │
└───────────────────────────┬────────────────────────────┘
                            │ (Validated Bar DataFrame)
                            ▼
┌────────────────────────────────────────────────────────┐
│     trading.indicators.TechnicalIndicatorEngine        │
│                                                        │
│ 1. Exponential Moving Averages (EMA 9, 21, 50, 200)    │
│ 2. Relative Strength Index (RSI 14)                    │
│ 3. Average True Range (ATR 14)                         │
│ 4. Average Directional Index (ADX 14, +DI, -DI)        │
│ 5. Deterministic Market Structure (Swings, HH/LL)      │
└───────────────────────────┬────────────────────────────┘
                            │ (DataFrame + Indicator Columns)
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Future Signal Engine                  │
│                    (Phase 6 Module)                    │
└────────────────────────────────────────────────────────┘
```

---

## 4. Indicator Implementation Details

### Exponential Moving Average (EMA)
- **Periods**: Configurable (`ema_fast: 9`, `ema_slow: 21`, `ema_trend: 50`, `ema_baseline: 200`).
- **Formula**: $\text{EMA}_t = \text{Price}_t \times \alpha + \text{EMA}_{t-1} \times (1 - \alpha)$, where $\alpha = \frac{2}{\text{period} + 1}$.
- **Warm-up**: First $\text{period}-1$ rows are explicitly set to `NaN`.

### Relative Strength Index (RSI)
- **Period**: Configurable (`rsi_period: 14`).
- **Formula**: Wilder's exponential smoothing ($\alpha = 1 / 14$) on price gains and losses; $RS = \frac{\text{AvgGain}}{\text{AvgLoss} + 1e-10}$; $\text{RSI} = 100 - \frac{100}{1 + RS}$.
- **Warm-up**: First $14$ rows are explicitly set to `NaN`.

### Average True Range (ATR)
- **Period**: Configurable (`atr_period: 14`).
- **Formula**: True Range $TR_t = \max(\text{High}_t - \text{Low}_t, |\text{High}_t - \text{Close}_{t-1}|, |\text{Low}_t - \text{Close}_{t-1}|)$; smoothed using Wilder's EMA ($\alpha = 1 / 14$).
- **Warm-up**: First $14$ rows are explicitly set to `NaN`.

### Average Directional Index (ADX)
- **Period**: Configurable (`adx_period: 14`).
- **Formula**: Computes $+DM$, $-DM$, $TR$, smooths via Wilder's EMA, calculates $+DI_{14}$, $-DI_{14}$, directional movement index $DX$, and final smoothed $ADX_{14}$.
- **Warm-up**: First $28$ rows are explicitly set to `NaN`.

### Market Structure
- **Swing Window**: Configurable (`swing_window: 5`).
- **Pivot Confirmation**: A bar $i$ is identified as a swing high if $\text{High}_i = \max(\text{High}_{i-5 : i+6})$ and is confirmed causally at bar $i+5$.
- **Structural States**: `BULLISH` (Higher-High confirmed), `BEARISH` (Lower-Low confirmed), or `NEUTRAL`.

---

## 5. Input / Output Schema & Configuration

- **Input Contract**: Validated DataFrame with `timestamps`, `open`, `high`, `low`, `close`, `volume`, `amount`.
- **Output Contract**: Input DataFrame appended with `ema_9`, `ema_21`, `ema_50`, `ema_200`, `rsi_14`, `atr_14`, `adx_14`, `plus_di_14`, `minus_di_14`, `market_structure_state`.
- **Configuration** (`config/config.yaml`):
```yaml
indicators:
  ema_fast: 9
  ema_slow: 21
  ema_trend: 50
  ema_baseline: 200
  rsi_period: 14
  adx_period: 14
  atr_period: 14
  swing_window: 5
```

---

## 6. Warm-up & No-Look-Ahead Verification

- **Warm-up Handling**: Preserves explicit `NaN` values during warm-up periods rather than imputing fake values.
- **No Future Leakage Proof**: Verified via `test_no_future_leakage_proof` in `tests/test_indicators.py`. Mutating price values after bar index $250$ produced 100% identical indicator values for bars $0$ through $250$.

---

## 7. Volume & Amount Distinction

- MT5 `tick_volume` is mapped to `volume` (never mislabeled as exchange volume).
- `amount` is mapped to `real_volume` or `volume * mean_price` to maintain schema compatibility with `KronosPredictor`.

---

## 8. Real MT5 Integration Test Status

```text
REAL MT5 INDICATOR TEST:
NOT TESTED
```

*(Reason: Sandbox environment is Linux; live MT5 terminal connection requires Windows OS. Indicator logic was 100% verified using deterministic unit and integration tests)*

---

## 9. Test Results

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
collecting ... collected 34 items

tests/test_foundation.py::test_required_directories_exist PASSED         [  2%]
tests/test_foundation.py::test_configuration_file_loads PASSED           [  5%]
tests/test_foundation.py::test_env_example_file_exists PASSED            [  8%]
tests/test_foundation.py::test_kronos_imports_remain_functional PASSED   [ 11%]
tests/test_foundation.py::test_trading_models_instantiation PASSED       [ 14%]
tests/test_mt5_connection.py::test_mt5_connection_initial_state PASSED   [ 17%]
tests/test_mt5_connection.py::test_mt5_connection_env_vars PASSED        [ 20%]
tests/test_mt5_connection.py::test_mt5_connection_missing_package_graceful_handling PASSED [ 23%]
tests/test_mt5_connection.py::test_mt5_connection_mocked_success PASSED  [ 26%]
tests/test_mt5_data.py::test_validation_successful PASSED                [ 29%]
tests/test_mt5_data.py::test_validation_insufficient_count PASSED        [ 32%]
tests/test_mt5_data.py::test_validation_malformed_ohlc PASSED            [ 35%]
tests/test_mt5_data.py::test_validation_duplicate_timestamps PASSED      [ 38%]
tests/test_mt5_data.py::test_validation_unordered_timestamps PASSED      [ 41%]
tests/test_mt5_data.py::test_get_closed_bars_mocked_success_and_forming_bar_exclusion PASSED [ 44%]
tests/test_mt5_data.py::test_get_closed_bars_empty_response PASSED       [ 47%]
tests/test_mt5_data.py::test_get_closed_bars_missing_mt5_package PASSED  [ 50%]
tests/test_kronos_adapter.py::test_adapter_initialization_defaults PASSED [ 52%]
tests/test_kronos_adapter.py::test_adapter_insufficient_candles_rejection PASSED [ 55%]
tests/test_kronos_adapter.py::test_adapter_missing_required_column_rejection PASSED [ 58%]
tests/test_kronos_adapter.py::test_adapter_mocked_prediction_success PASSED [ 61%]
tests/test_kronos_adapter.py::test_real_kronos_model_inference PASSED    [ 64%]
tests/test_indicators.py::test_ema_calculation_and_warmup PASSED         [ 67%]
tests/test_indicators.py::test_rsi_calculation_and_bounds PASSED         [ 70%]
tests/test_indicators.py::test_atr_calculation PASSED                    [ 73%]
tests/test_indicators.py::test_adx_calculation PASSED                    [ 76%]
tests/test_indicators.py::test_market_structure_identification PASSED    [ 79%]
tests/test_indicators.py::test_no_future_leakage_proof PASSED            [ 82%]
tests/test_indicators.py::test_insufficient_history_handling PASSED      [ 85%]
tests/test_indicators.py::test_calculate_all_indicators_integration_400_closed_bars PASSED [ 88%]
tests/test_kronos_regression.py::test_kronos_predictor_regression[512] PASSED [ 91%]
tests/test_kronos_regression.py::test_kronos_predictor_regression[256] PASSED [ 94%]
tests/test_kronos_regression.py::test_kronos_predictor_mse[512-0.008979] PASSED [ 97%]
tests/test_kronos_regression.py::test_kronos_predictor_mse[256-0.003741] PASSED [100%]

======================== 34 passed, 1 warning in 53.48s ========================
```

- **Total Test Count**: 34
- **Passed**: 34
- **Failed**: 0
- **Duration**: 53.48s

---

## 10. Safety & Core Model Protection Confirmations

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

## 11. Final Status Assessment

```text
PHASE 5 STATUS:
COMPLETE

INDICATOR ENGINE:
COMPLETE

EMA:
PASSED

RSI:
PASSED

ADX:
PASSED

ATR:
PASSED

MARKET STRUCTURE:
PASSED

NO LOOK-AHEAD:
PASSED

CLOSED-CANDLE:
PASSED

TESTS:
34 PASSED / 0 FAILED

FULL REGRESSION:
34 PASSED / 0 FAILED

CORE KRONOS MODEL:
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

READY FOR PHASE 6:
YES
```
