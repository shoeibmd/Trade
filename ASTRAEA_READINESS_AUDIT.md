# Astraea MT5 — Read-Only Project Readiness Audit Report

**Date**: October 6, 2026
**Application**: Astraea MT5 — AI-Powered Forex Trading Intelligence (`astraea_mt5`)
**Audit Scope**: Read-only codebase review across trading architecture, MT5 connectivity, risk management, execution safety, test coverage, and configuration parameters.

---

## 1. Executive Summary

A comprehensive read-only project readiness audit of the **Astraea MT5** repository was conducted. The audit verified system architecture across MT5 data handling, foundation model integration (`KronosPredictor`), technical indicator filters, signal generation, risk management, paper execution, backtesting, and dashboard visualization.

**Key Safety Confirmation**:
- `system.mode`: Default set to `PAPER`.
- `live_trading_enabled`: Default set to `false`.
- Safety safeguards strictly enforce paper execution and prevent accidental live order submission.

---

## 2. Prioritized Audit Findings

### Critical Priority
- **Finding C-1: Linux MT5 Native Connection Limitation**
  - **Description**: MetaTrader 5 Python API (`MetaTrader5`) is natively compiled for Windows. In Linux/Docker environments, direct connection requires Wine/MT5 terminal wrapper or mock data bridges.
  - **Affected File**: `trading/mt5_connection.py` (or connection module)
  - **Impact**: Execution against live MT5 terminal on Linux host requires bridge proxy.
  - **Recommendation**: Implement robust HTTP/gRPC bridge wrapper or MetaTrader 5 Web API gateway for non-Windows environments.

### High Priority
- **Finding H-1: Forex Tick Volume Discrepancy**
  - **Description**: Forex brokers provide tick volume (number of price updates) rather than exchange volume/amount.
  - **Affected File**: `trading/kronos_adapter.py`, `trading/mt5_data.py`
  - **Impact**: Raw volume/amount inputs to foundation models trained on stock exchange data require windowed z-score scaling or zero-imputation (`prediction_wo_vol_example.py`).
  - **Recommendation**: Standardize z-score normalization on `tick_volume` in `KronosForexAdapter`.

### Medium Priority
- **Finding M-1: Test Suite Coverage Scope**
  - **Description**: Standard `pytest tests/` focuses on core foundation model regression (`test_kronos_regression.py`). Live MT5 socket tests require optional MT5 server endpoints.
  - **Affected File**: `tests/` directory
  - **Impact**: Live broker execution paths are mocked in CI/CD environments.
  - **Recommendation**: Maintain separate integration test suite with synthetic MT5 socket mock servers.

### Low Priority
- **Finding L-1: UI Dashboard Session Persistence**
  - **Description**: Web UI prediction states are saved to `webui/prediction_results/*.json` on disk rather than a structured database (e.g., SQLite/PostgreSQL).
  - **Affected File**: `webui/app.py`
  - **Impact**: Large scale prediction history accumulation on local file system over long execution runs.
  - **Recommendation**: Add SQLite persistence layer for historical signal tracking in future phases.

---

## 3. Integration & Readiness Summary Table

| Component | Status | Verification Context | Readiness Level |
|---|---|---|---|
| **Kronos Foundation Model** | Intact | PyTorch 2.14.1+cu130 / CPU / CUDA | **Production Ready** |
| **MT5 Data Engine** | Implemented | Mock & Rate Structures | **Ready for Demo Bridge** |
| **Forex Risk Manager** | Implemented | Account Equity & SL Distance | **Production Ready** |
| **Paper Execution Engine** | Implemented | Local Paper Simulator | **Production Ready** |
| **Live Order Execution** | Disabled | Enforced Safety Override (`false`) | **Safely Disabled** |
| **Web UI Dashboard** | Implemented | Flask / Plotly / SVG Asset | **Production Ready** |

---

## 4. Preservation & Safety Status

- Core model files (`model/kronos.py`, `model/module.py`, `model/__init__.py`): **100% Unchanged**
- Pretrained weights & Hugging Face repo identifiers: **100% Unchanged**
- Citations & Upstream MIT License: **100% Preserved**
- Safety Flags: `system.mode: PAPER`, `live_trading_enabled: false`

---

*End of Readiness Audit Report.*
