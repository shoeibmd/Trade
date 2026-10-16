# Astraea MT5 — Troubleshooting Guide

## Common Issues & Solutions

### 1. `ImportError: cannot import name 'SignalDirection' from 'trading.models'`
- **Symptom**: Import error when launching application or tests.
- **Cause**: Import mismatch where `SignalDirection` alias was missing in `trading/models.py`.
- **Solution**: Resolved in codebase (`SignalDirection = SignalType`).

### 2. `ModuleNotFoundError: No module named 'trading.kronos_adapter'`
- **Symptom**: Test collection error when executing legacy backtester tests.
- **Cause**: File was renamed to `trading/forex_adapter.py`.
- **Solution**: Resolved in codebase via re-export module `trading/kronos_adapter.py`.

### 3. MT5 Terminal Connection Failure on Linux
- **Symptom**: `MetaTrader5 Python package is not installed`.
- **Cause**: Native `MetaTrader5` package requires Windows OS.
- **Solution**: Set `MT5_MODE=GATEWAY` in `.env` to connect via `MT5GatewayClient` to a Windows REST proxy.

### 4. Slow Strategy Optimizer Grid Searches
- **Symptom**: Optimizer execution takes long on CPU.
- **Solution**: Enable in-memory forecast caching (`adapter.cache_enabled = True`).
