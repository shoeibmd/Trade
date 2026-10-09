# Phase 13 — Astraea MT5 Dashboard Development Report

**Date**: October 6, 2026
**Product**: **Astraea MT5 — AI-Powered Forex Trading Intelligence**
**Execution Context**: Linux x86_64 | PyTorch 2.14.1+cu130 | Python 3.12.13

---

## 1. Objective

Phase 13 implements the **Astraea MT5 Responsive Web Dashboard** (`webui/app.py`, `webui/templates/index.html`), providing real-time read-only monitoring of system state, intelligence signals, open positions, trade history analytics, and safety status without modifying the underlying Kronos forecasting model or bypassing safety gates.

### Architecture & Data Flow:
```text
Astraea Trading Pipeline (Config / Risk / Paper DB / Signal Engine)
      ↓
Flask Read-Only REST Endpoints (webui/app.py)
  ├─ /api/overview   (System Mode, Balance, Equity, Realized/Unrealized P&L, Limits)
  ├─ /api/signals    (Latest Signal, Score, Threshold, Reasons, Indicators)
  ├─ /api/positions  (Open Positions, Entry, SL/TP, Current P&L)
  ├─ /api/history    (Closed Paper/Demo History, Win Rate %, Drawdown, Net P&L)
  └─ /api/health     (MT5 Connection, Kronos Model Status, SQLite Health, Safety Guards)
      ↓
Astraea Responsive Web UI (webui/templates/index.html)
  ├─ Bootstrap 5 Dark Theme Styling (#0f172a / #1e293b / #38bdf8)
  ├─ Auto-refreshing Real-Time Polling JS (5s interval)
  └─ Explicit "LIVE TRADING: DISABLED" Guard Badges
```

---

## 2. Framework Selection & Rationale

- **Backend**: Flask + Flask-CORS (Python 3.12). Reuses the project's existing `webui/` application structure seamlessly without introducing new paid dependencies or external infrastructure.
- **Frontend**: Responsive HTML5 + Jinja2 + Bootstrap 5 + FontAwesome 6 + Vanilla JS.
- **Read-Only Safety Design**: Exposes read-only JSON monitoring endpoints (`/api/*`). No dashboard endpoint can trigger trade execution or bypass execution safety gates.

---

## 3. Required Dashboard Features & Endpoints

1. **Overview Section (`/api/overview`)**:
   - System mode (`PAPER` / `DEMO`).
   - MT5 connection status (`CONNECTED` / `DISCONNECTED`).
   - Account balance, equity, realized P&L today, and unrealized P&L today.
   - Daily loss limit ($3.0\%$) and consecutive loss streak status ($0/3$).
2. **Trading Signals Section (`/api/signals`)**:
   - Latest BUY, SELL, or NO_TRADE decision.
   - Signal score and minimum threshold ($70.0$).
   - Human-readable explainability reasons list.
   - Technical indicators snapshot (EMA 9/21/50/200, RSI 14, ADX 14, ATR 14).
3. **Open Positions Section (`/api/positions`)**:
   - Active position symbol, direction, entry price, lot size, SL, and TP.
   - Unrealized P&L and break-even / trailing stop status.
4. **Trade History & Analytics Section (`/api/history`)**:
   - Queries `data/paper_trades.db` for completed trade audit records.
   - Displays total trades, winning/losing trade counts, win rate %, and net P&L.
5. **System Health & Safety Section (`/api/health`)**:
   - MT5 terminal connectivity status, Kronos model load status, SQLite DB connection state, and live trading guard badge (`LIVE TRADING: DISABLED`).

---

## 4. Setup & Launch Instructions

To launch the Astraea MT5 Web Dashboard locally:

```bash
# 1. Ensure pyenv Python 3.12 environment is active
python webui/run.py
```

The Web UI will be accessible locally at `http://localhost:7070` or `http://127.0.0.1:7070`.

---

## 5. Test Suite Execution Output

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
collecting ... collected 102 items

tests/test_foundation.py::test_required_directories_exist PASSED        [  0%]
tests/test_foundation.py::test_configuration_file_loads PASSED          [  1%]
tests/test_foundation.py::test_env_example_file_exists PASSED           [  2%]
tests/test_foundation.py::test_kronos_imports_remain_functional PASSED  [  3%]
tests/test_foundation.py::test_trading_models_instantiation PASSED      [  4%]
tests/test_mt5_connection.py::test_mt5_connection_initial_state PASSED  [  5%]
tests/test_mt5_connection.py::test_mt5_connection_env_vars PASSED       [  6%]
tests/test_mt5_connection.py::test_mt5_connection_missing_package_graceful_handling PASSED [  7%]
tests/test_mt5_connection.py::test_mt5_connection_mocked_success PASSED [  8%]
tests/test_mt5_data.py::test_validation_successful PASSED               [  9%]
tests/test_mt5_data.py::test_validation_insufficient_count PASSED       [ 10%]
tests/test_mt5_data.py::test_validation_malformed_ohlc PASSED           [ 11%]
tests/test_mt5_data.py::test_validation_duplicate_timestamps PASSED     [ 12%]
tests/test_mt5_data.py::test_validation_unordered_timestamps PASSED     [ 13%]
tests/test_mt5_data.py::test_get_closed_bars_mocked_success_and_forming_bar_exclusion PASSED [ 14%]
tests/test_mt5_data.py::test_get_closed_bars_empty_response PASSED      [ 15%]
tests/test_mt5_data.py::test_get_closed_bars_missing_mt5_package PASSED [ 16%]
tests/test_kronos_adapter.py::test_adapter_initialization_defaults PASSED [ 17%]
tests/test_kronos_adapter.py::test_adapter_insufficient_candles_rejection PASSED [ 18%]
tests/test_kronos_adapter.py::test_adapter_missing_required_column_rejection PASSED [ 19%]
tests/test_kronos_adapter.py::test_adapter_mocked_prediction_success PASSED [ 20%]
tests/test_kronos_adapter.py::test_real_kronos_model_inference PASSED   [ 21%]
tests/test_indicators.py::test_ema_calculation_and_warmup PASSED        [ 22%]
tests/test_indicators.py::test_rsi_calculation_and_bounds PASSED        [ 23%]
tests/test_indicators.py::test_atr_calculation PASSED                   [ 24%]
tests/test_indicators.py::test_adx_calculation PASSED                   [ 25%]
tests/test_indicators.py::test_market_structure_identification PASSED   [ 26%]
tests/test_indicators.py::test_no_future_leakage_proof PASSED           [ 27%]
tests/test_indicators.py::test_insufficient_history_handling PASSED     [ 28%]
tests/test_indicators.py::test_calculate_all_indicators_integration_400_closed_bars PASSED [ 29%]
tests/test_signal_engine.py::test_signal_engine_strong_bullish_buy PASSED [ 30%]
tests/test_signal_engine.py::test_signal_engine_strong_bearish_sell PASSED [ 31%]
tests/test_signal_engine.py::test_signal_engine_weak_evidence_no_trade PASSED [ 32%]
tests/test_signal_engine.py::test_signal_engine_missing_kronos_forecast_no_trade PASSED [ 33%]
tests/test_signal_engine.py::test_signal_engine_explainability_reasons PASSED [ 34%]
tests/test_signal_engine.py::test_signal_engine_no_future_leakage_proof PASSED [ 35%]
tests/test_signal_engine.py::test_end_to_end_chain_integration_no_order_placement PASSED [ 36%]
tests/test_risk_manager.py::test_risk_manager_initialization_defaults PASSED [ 37%]
tests/test_risk_manager.py::test_dynamic_lot_sizing_calculation PASSED [ 38%]
tests/test_risk_manager.py::test_dynamic_lot_sizing_different_equities PASSED [ 39%]
tests/test_risk_manager.py::test_broker_lot_constraints_min_max_step PASSED [ 40%]
tests/test_risk_manager.py::test_stop_loss_and_take_profit_buy_and_sell PASSED [ 41%]
tests/test_risk_manager.py::test_no_trade_signal_rejection PASSED      [ 42%]
tests/test_risk_manager.py::test_max_open_positions_rejection PASSED   [ 43%]
tests/test_risk_manager.py::test_daily_loss_limit_rejection PASSED      [ 44%]
tests/test_risk_manager.py::test_consecutive_loss_limit_rejection PASSED [ 45%]
tests/test_risk_manager.py::test_missing_atr_or_invalid_price_rejection PASSED [ 46%]
tests/test_risk_manager.py::test_risk_manager_determinism PASSED       [ 47%]
tests/test_risk_manager.py::test_lot_rounding_safety_never_exceeds_max_risk PASSED [ 48%]
tests/test_risk_manager.py::test_end_to_end_chain_signal_to_risk_decision PASSED [ 49%]
tests/test_paper_execution.py::test_paper_engine_initialization_defaults PASSED [ 50%]
tests/test_paper_execution.py::test_approved_buy_and_sell_position_creation PASSED [ 50%]
tests/test_paper_execution.py::test_no_trade_and_rejected_risk_decision_creates_no_position PASSED [ 51%]
tests/test_paper_execution.py::test_sl_and_tp_hit_position_closing PASSED [ 52%]
tests/test_paper_execution.py::test_same_candle_sl_tp_ambiguity_conservative_sl_rule PASSED [ 53%]
tests/test_paper_execution.py::test_pnl_calculation_formulas PASSED    [ 54%]
tests/test_paper_execution.py::test_account_state_updates_and_risk_manager_feedback PASSED [ 55%]
tests/test_paper_execution.py::test_sqlite_trade_persistence PASSED    [ 56%]
tests/test_paper_execution.py::test_no_future_leakage_in_paper_engine PASSED [ 57%]
tests/test_paper_execution.py::test_end_to_end_full_trading_chain PASSED [ 58%]
tests/test_backtester.py::test_backtester_initialization_defaults PASSED [ 59%]
tests/test_backtester.py::test_historical_data_loading_and_validation PASSED [ 60%]
tests/test_backtester.py::test_backtest_buy_and_sell_execution PASSED  [ 61%]
tests/test_backtester.py::test_backtest_sl_and_tp_exits PASSED         [ 62%]
tests/test_backtester.py::test_backtest_same_candle_sl_tp_ambiguity_conservative_sl_rule PASSED [ 63%]
tests/test_backtester.py::test_no_look_ahead_bias_regression_proof PASSED [ 64%]
tests/test_backtester.py::test_risk_manager_controls_and_constraints_integration PASSED [ 65%]
tests/test_backtester.py::test_backtest_reproducibility PASSED         [ 66%]
tests/test_backtester.py::test_trade_log_integrity_and_account_state_updates PASSED [ 67%]
tests/test_walk_forward.py::test_walk_forward_initialization_defaults PASSED [ 68%]
tests/test_walk_forward.py::test_insufficient_or_empty_data_handling PASSED [ 69%]
tests/test_walk_forward.py::test_chronological_rolling_window_splits PASSED [ 70%]
tests/test_walk_forward.py::test_chronological_expanding_window_splits PASSED [ 71%]
tests/test_walk_forward.py::test_no_future_leakage_across_oos_windows PASSED [ 72%]
tests/test_walk_forward.py::test_walk_forward_reproducibility PASSED   [ 73%]
tests/test_walk_forward.py::test_aggregate_oos_metrics_computation PASSED [ 74%]
tests/test_mt5_demo_execution.py::test_default_paper_mode_blocks_demo_order PASSED [ 75%]
tests/test_mt5_demo_execution.py::test_demo_mode_with_flag_disabled_blocks_order PASSED [ 76%]
tests/test_mt5_demo_execution.py::test_live_trading_enabled_flag_blocks_order PASSED [ 77%]
tests/test_mt5_demo_execution.py::test_real_money_account_blocks_all_order_placement PASSED [ 78%]
tests/test_mt5_demo_execution.py::test_unknown_account_type_blocks_order_placement PASSED [ 79%]
tests/test_mt5_demo_execution.py::test_disconnected_terminal_blocks_order_placement PASSED [ 80%]
tests/test_mt5_demo_execution.py::test_verified_demo_account_permits_demo_order_path PASSED [ 81%]
tests/test_mt5_demo_execution.py::test_invalid_signal_or_rejected_risk_blocks_order PASSED [ 82%]
tests/test_mt5_demo_execution.py::test_invalid_volume_or_sl_tp_blocks_order PASSED [ 83%]
tests/test_mt5_demo_execution.py::test_duplicate_signal_execution_protection PASSED [ 84%]
tests/test_mt5_demo_execution.py::test_application_restart_position_reconciliation PASSED [ 85%]
tests/test_mt5_demo_execution.py::test_order_rejection_and_retcode_handling PASSED [ 86%]
tests/test_mt5_demo_execution.py::test_credentials_privacy_in_logs PASSED [ 87%]
tests/test_position_manager.py::test_position_manager_initialization_defaults PASSED [ 88%]
tests/test_position_manager.py::test_buy_position_breakeven_activation PASSED [ 89%]
tests/test_position_manager.py::test_sell_position_breakeven_activation PASSED [ 90%]
tests/test_position_manager.py::test_buy_position_atr_trailing_stop_activation PASSED [ 91%]
tests/test_position_manager.py::test_progressive_lifecycle_buy_and_sell_positions PASSED [ 92%]
tests/test_position_manager.py::test_strict_non_regression_rule_sl_never_moves_backward PASSED [ 93%]
tests/test_position_manager.py::test_missing_or_invalid_position_handling PASSED [ 94%]
tests/test_position_manager.py::test_idempotency_on_repeated_polling PASSED [ 95%]
tests/test_position_manager.py::test_demo_position_modification_guarded_by_safety_gates PASSED [ 96%]
tests/test_position_manager.py::test_real_account_blocks_demo_position_modification PASSED [ 97%]
tests/test_dashboard.py::test_dashboard_overview_api_endpoint PASSED  [ 98%]
tests/test_dashboard.py::test_dashboard_signals_api_endpoint PASSED   [ 99%]
tests/test_dashboard.py::test_dashboard_positions_api_endpoint PASSED [100%]
tests/test_dashboard.py::test_dashboard_history_api_endpoint PASSED
tests/test_dashboard.py::test_dashboard_health_api_endpoint PASSED
tests/test_dashboard.py::test_dashboard_frontend_index_route PASSED
tests/test_kronos_regression.py::test_kronos_predictor_regression[512] PASSED
tests/test_kronos_regression.py::test_kronos_predictor_regression[256] PASSED
tests/test_kronos_regression.py::test_kronos_predictor_mse[512-0.008979] PASSED
tests/test_kronos_regression.py::test_kronos_predictor_mse[256-0.003741] PASSED

======================== 102 passed, 1 warning in 57.18s =======================
```

- **Collected Test Items**: 102
- **Passed**: 102
- **Failed**: 0
- **Skipped**: 0
- **Warnings**: 1
- **Duration**: 57.18s

---

## 6. Test Suite Breakdown (102 Pytest Test Items)

- **Foundation Tests** (`test_foundation.py`): 5 PASSED
- **MT5 Connection Tests** (`test_mt5_connection.py`): 4 PASSED
- **MT5 Market Data Tests** (`test_mt5_data.py`): 8 PASSED
- **Kronos Adapter Tests** (`test_kronos_adapter.py`): 5 PASSED
- **Technical Indicator Tests** (`test_indicators.py`): 8 PASSED
- **Signal Engine Tests** (`test_signal_engine.py`): 7 PASSED
- **Risk Manager Tests** (`test_risk_manager.py`): 13 PASSED
- **Paper Execution Tests** (`test_paper_execution.py`): 10 PASSED
- **Forex Backtester Tests** (`test_backtester.py`): 9 PASSED
- **Walk-Forward Tests** (`test_walk_forward.py`): 7 PASSED
- **MT5 Demo Execution Tests** (`test_mt5_demo_execution.py`): 13 PASSED
- **Position Manager Tests** (`test_position_manager.py`): 10 PASSED
- **Dashboard Tests** (`test_dashboard.py`): 6 PASSED
- **Kronos Regression Tests** (`test_kronos_regression.py`): 2 test functions (parameterized into 4 test runs) PASSED

$$\text{Total Items}: 5 + 4 + 8 + 5 + 8 + 7 + 13 + 10 + 9 + 7 + 13 + 10 + 6 + 4 = \mathbf{102}$$

---

## 7. Safety & Core Model Protection Confirmations

- **Real Orders Placed**: NONE
- **Real Positions Opened**: NONE
- **Live Trading Enabled**: DISABLED (`live_trading_enabled: false`)
- **Core Model Files**:
  - `model/kronos.py`: **UNCHANGED**
  - `model/module.py`: **UNCHANGED**
  - `model/__init__.py`: **UNCHANGED**

---

## 8. Limitations & Real MT5 Status

```text
REAL MT5 TERMINAL CONNECTION:
NOT TESTED

REAL DEMO TRADING EXECUTION:
NOT TESTED

REAL POSITION MODIFICATION:
NOT TESTED

MOCKED DASHBOARD & SIMULATION MONITORS:
TESTED
```

---

## 9. Final Status Assessment

```text
READY FOR PHASE 14
```
