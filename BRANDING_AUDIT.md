# Astraea MT5 — Branding & Controlled Rename Audit Report

**Date**: October 6, 2026
**Application Name**: Astraea MT5 — AI-Powered Forex Trading Intelligence
**Short Name**: Astraea
**Technical ID**: `astraea_mt5`
**Underlying Model**: Kronos Foundation Model (`Kronos`, `KronosTokenizer`, `KronosPredictor`)

---

## 1. Executive Summary

A controlled rename and audit was executed to standardize the product identity as **Astraea MT5 — AI-Powered Forex Trading Intelligence**.

### Controlled Renames Applied (Phase 1 Approved):
- `trading/kronos_adapter.py` → `trading/forex_adapter.py`
- `tests/test_kronos_adapter.py` → `tests/test_forex_adapter.py`
- Updated dependent module imports in `trading/backtester.py`, `tests/test_mt5_data.py`, and `tests/test_forex_adapter.py`.

### Unchanged Protected Components (Phase 2 Preserved):
- `model/kronos.py`, `model/module.py`, `model/__init__.py`
- `tests/test_kronos_regression.py`
- Pretrained model class names (`Kronos`, `KronosTokenizer`, `KronosPredictor`)
- Hugging Face model identifiers (`NeoQuasar/Kronos-small`, `NeoQuasar/Kronos-base`, etc.)
- Paper citations and upstream MIT License
- Safe system settings (`live_trading_enabled: false`, `system.mode: PAPER`)

---

## 2. Updated Files Summary

| File Path | Action | Purpose |
|---|---|---|
| `trading/forex_adapter.py` | Renamed from `trading/kronos_adapter.py` | Application adapter interfacing MT5 bar data with Kronos foundation model. |
| `tests/test_forex_adapter.py` | Renamed from `tests/test_kronos_adapter.py` | Unit test suite for Forex adapter. |
| `trading/backtester.py` | Import Updated | Imports `KronosAdapter` from `trading.forex_adapter`. |
| `tests/test_mt5_data.py` | Import Updated | Imports `KronosAdapter` from `trading.forex_adapter`. |
| `README.md` | Product Branding Verified | Astraea MT5 product branding and Kronos attribution. |
| `webui/templates/index.html` | UI Branding Verified | Astraea MT5 dashboard header, titles, and logo banner. |
| `webui/app.py` | Web Backend Verified | Branding asset serving and startup logs. |

---

## 3. Preserved Historical & Model References (Phase 3 Preserved)

The following files were intentionally preserved without renaming to maintain historical accuracy and compatibility:
- `PHASE_0_ANALYSIS_REPORT.md` (Phase 0 repository trace document)
- `PHASE_4_FORECASTING_REPORT.md` (Phase 4 model report)
- `examples/run_backtest_kronos.py` (Stock backtesting example script)
- `examples/kronos_demo.py` (Demo script)
- `examples/yuce/run_backtest_kronos_output.json` (Historical report output)

---

## 4. Test & Safety Verification

- **Test Suite Executed**: `pytest tests/test_forex_adapter.py tests/test_mt5_data.py tests/test_mt5_connection.py tests/test_kronos_regression.py`
- **Result**: **9 passed, 0 failed (100% pass rate)**.
- **Safety Flags Enforced**:
  - `system.mode`: `PAPER`
  - `live_trading_enabled`: `false`

---

*End of Branding & Controlled Rename Audit Report.*
