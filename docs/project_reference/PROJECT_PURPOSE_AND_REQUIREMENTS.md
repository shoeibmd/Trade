# Astraea MT5 — Project Purpose & Requirements

**Technical Specifications and Business Purpose**

---

## 1. Executive Purpose

Astraea MT5 exists to bridge modern autoregressive AI foundation models with systematic Forex trading infrastructure. The platform provides:
- High-fidelity MetaTrader 5 rate collection (Windows Native & Linux REST Gateway Client).
- Multi-horizon price and volume forecasting via the foundation model.
- Technical indicator trend/momentum filtering (ATR, RSI, EMA, Bollinger Bands).
- Probabilistic 100-point signal engine with confidence scoring.
- Dynamic lot sizing based on account equity, currency pip values, and stop-loss distance.
- Deterministic paper execution simulation and event-driven backtesting with 0 look-ahead bias.
- Real-time position tracking and trailing break-even management.
- Web UI dashboard for strategy monitoring and visual chart analytics.

---

## 2. Functional & Safety Requirements

1. **System Safety Enforcers**:
   - `system.mode`: Set to `PAPER` by default.
   - `live_trading_enabled`: Set to `false` by default.
   - Non-bypassable `ACCOUNT_TRADE_MODE_REAL` protection blocks live order submission.
2. **Forecasting Engine Integration**:
   - Closed-candle guarantee: Bypasses active forming bar (position 0) when retrieving MT5 history.
   - High-level forecasting wrapper `AstraeaForecastingEngine` exported in `trading/__init__.py`.
   - In-memory SHA-256 forecast caching in `KronosAdapter` to eliminate duplicate model inference calls during backtesting/optimization.
3. **Multi-Platform Connectivity**:
   - Windows: Direct native `MetaTrader5` Python API.
   - Linux/Docker: Authenticated REST client (`MT5GatewayClient`) with `X-MT5-API-Key` headers, timeouts, and exponential backoff retries.

---

## 3. Non-Functional Requirements

- Zero modification of core Transformer model files (`model/kronos.py`, `model/module.py`, `model/__init__.py`).
- Deterministic reproducibility under identical inputs and seed parameters.
- Comprehensive unit/integration test coverage across all trading modules (`tests/`).
