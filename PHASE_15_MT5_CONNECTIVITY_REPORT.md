# Astraea MT5 — Phase 15 Report: MT5 Connectivity & Read-Only Integration

**Date**: October 6, 2026
**Phase**: Phase 15 — Resolve MT5 Connectivity and Validate Read-Only Integration
**Application**: Astraea MT5 — AI-Powered Forex Trading Intelligence (`astraea_mt5`)

---

## 1. Executive Summary

Phase 15 addressed the Critical MT5 connectivity architecture finding and High tick-volume normalization requirement without altering core model code, pretrained weights, or safety settings:

1. **Dual-Mode MT5 Connectivity Gateway (`trading/mt5_connection.py`)**:
   - **Windows Environment**: Native `MetaTrader5` Python API integration for local Windows terminals.
   - **Linux / Docker Environment**: Authenticated REST/JSON Gateway Client (`MT5GatewayClient`) connecting securely to a Windows-hosted MT5 gateway using `X-MT5-API-Key` headers, configurable timeouts, and exponential backoff retries.
2. **Configurable Forex Tick Volume Normalization (`trading/kronos_adapter.py`)**:
   - Implemented opt-in, windowed z-score tick-volume preprocessing with configurable clipping `[-5.0, 5.0]`, zero-variance protection, and NaN imputation. Disabled by default to preserve baseline model input distribution until user-configured.
3. **Automated Testing & Mock Validation**:
   - Added unit and integration tests in `tests/test_mt5_connection.py` and `tests/test_mt5_data.py`. Passed 100% of connection, gateway authentication, candle validation, and regression tests.
   - Live Windows MT5 terminal validation is marked as `PENDING_WINDOWS_TERMINAL` until run on a live Windows host.
4. **Safety Verification**:
   - `system.mode: PAPER`
   - `live_trading_enabled: false`
   - No demo or live trade orders were placed or modified.

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                   METATRADER 5 TERMINAL                 │
│                 (Windows Desktop Terminal)              │
└───────────────────────────┬────────────────────────────┘
                            │ (Local API or Gateway Proxy)
                            ▼
┌────────────────────────────────────────────────────────┐
│               MT5 CONNECTION GATEWAY                   │
│   Native MT5 (Windows) / MT5GatewayClient (Linux)     │
└───────────────────────────┬────────────────────────────┘
                            │ (Validated Bar DataFrame)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 KRONOS FOREX ADAPTER                   │
│         (Configurable Tick Volume Preprocessing)       │
└───────────────────────────┬────────────────────────────┘
                            │ (Formats x_df & Timestamps)
                            ▼
┌────────────────────────────────────────────────────────┐
│               EXISTING KRONOS PREDICTOR                │
│              (UNTOUCHED model/kronos.py)               │
└────────────────────────────────────────────────────────┘
```

---

## 3. Changed Files & Setup Instructions

### Modified Files:
- `trading/mt5_connection.py`: Added `MT5ConnectionMode` and `MT5GatewayClient`.
- `trading/kronos_adapter.py`: Added configurable `normalize_tick_volume` parameter and windowed z-score scaling.
- `tests/test_mt5_connection.py`: Added gateway authentication, ping, and mode tests.
- `tests/test_mt5_data.py`: Added tick-volume preprocessing unit tests.
- `ASTRAEA_READINESS_AUDIT.md`: Updated resolution status of Findings C-1 and H-1.

### Configuration (`config/.env` or Environment Variables):
```bash
MT5_MODE=GATEWAY # GATEWAY on Linux/Docker, NATIVE on Windows
MT5_GATEWAY_URL=http://<windows-host-ip>:8080
MT5_GATEWAY_API_KEY=your-secure-api-key-here
```

---

## 4. Test Results

- **Command Executed**: `/home/jules/.pyenv/versions/3.12.13/bin/pytest tests/test_mt5_connection.py tests/test_mt5_data.py tests/test_kronos_regression.py`
- **Collected**: 9 tests
- **Passed**: 9 tests (100% pass rate)
- **Failed / Skipped**: 0 / 0
- **Real Terminal Status**: `PENDING_WINDOWS_TERMINAL` (Tested via comprehensive mocks on Linux).

---

*End of Phase 15 Report.*
