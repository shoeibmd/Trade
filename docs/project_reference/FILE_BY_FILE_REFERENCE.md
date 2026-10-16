# Astraea MT5 — File-by-File Reference

**Core Subsystem File Mapping & Responsibilities**

---

## 1. Trading Subsystem (`trading/`)

- `trading/__init__.py`: Exports `AstraeaForecastingEngine`, `KronosAdapter`, `SignalType`, `SignalDirection`, and `PredictionResult`.
- `trading/models.py`: Defines core data classes (`TickData`, `BarData`, `PredictionResult`, `TradingSignal`, `Position`, `SignalType`, `SignalDirection`).
- `trading/mt5_connection.py`: Manages MT5 connections in dual mode (Native Windows `MetaTrader5` API / Linux REST `MT5GatewayClient`).
- `trading/mt5_data.py`: Fetches and validates closed market bars, enforces 400-bar history, and provides `validate_data` alias.
- `trading/forex_adapter.py`: Implements `AstraeaForecastingEngine` and `KronosAdapter` with bounded in-memory SHA-256 forecast caching.
- `trading/kronos_adapter.py`: Re-export wrapper module maintaining backward compatibility.
- `trading/indicators.py`: Computes ATR, RSI, EMA (20/50/200), and Bollinger Bands over OHLC DataFrames.
- `trading/signal_engine.py`: Evaluates 100-point probabilistic signal scores based on foundation predictions and technical indicators.
- `trading/risk_manager.py`: Calculates lot sizing based on account equity, currency pip value, and stop-loss distance.
- `trading/paper_execution.py`: Simulates paper trade executions, tracks unrealized/realized PnL, and updates account equity.
- `trading/backtester.py`: Event-driven Forex backtester with zero look-ahead bias and chronological bar evaluation.
- `trading/walk_forward.py`: Out-of-sample walk-forward optimizer evaluating strategy robustness over rolling time windows.
- `trading/mt5_demo_execution.py`: Order execution engine enforcing 9 safety gates (`system.mode: PAPER`, `live_trading_enabled: false`, real-account blocking).
- `trading/position_manager.py`: Live position tracker providing trailing break-even stop loss management.
- `trading/strategy_optimizer.py`: Grid-search strategy parameter optimizer.

---

## 2. Web UI Dashboard Subsystem (`webui/`)

- `webui/app.py`: Flask web backend serving REST endpoints (`/api/data-files`, `/api/load-model`, `/api/predict`, `/assets/branding/`).
- `webui/templates/index.html`: Single-page Plotly/JS dashboard interface with Astraea MT5 branding banner logo and interactive controls.

---

## 3. Untouched Model Subsystem (`model/`)

- `model/kronos.py`: Core Transformer model and tokenizer implementation.
- `model/module.py`: Neural network modules (`BSQuantizer`, `MultiHeadAttentionWithRoPE`, `RMSNorm`).
- `model/__init__.py`: Model package exports.
