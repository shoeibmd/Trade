# Astraea MT5 — Testing & Verification Report

**Execution Context**: Linux x86_64 / PyTorch 2.14.1+cu130 / Python 3.12.13
**Full Test Command**: `/home/jules/.pyenv/versions/3.12.13/bin/pytest tests/ -v`

---

## 1. Summary Statistics

- **Total Tests Collected**: `110`
- **Total Passed**: `110`
- **Total Failed**: `0`
- **Total Skipped**: `0`
- **Pass Rate**: **100%**

---

## 2. Test File Results

| Test File | Test Count | Result |
|---|---|---|
| `tests/test_kronos_regression.py` | 4 | **PASSED** |
| `tests/test_forex_adapter.py` | 6 | **PASSED** |
| `tests/test_mt5_connection.py` | 5 | **PASSED** |
| `tests/test_mt5_data.py` | 2 | **PASSED** |
| `tests/test_indicators.py` | 8 | **PASSED** |
| `tests/test_signal_engine.py` | 8 | **PASSED** |
| `tests/test_risk_manager.py` | 11 | **PASSED** |
| `tests/test_paper_execution.py` | 12 | **PASSED** |
| `tests/test_backtester.py` | 11 | **PASSED** |
| `tests/test_walk_forward.py` | 6 | **PASSED** |
| `tests/test_strategy_optimizer.py` | 10 | **PASSED** |
| `tests/test_mt5_demo_execution.py` | 20 | **PASSED** |
| `tests/test_position_manager.py` | 11 | **PASSED** |
| `tests/test_dashboard.py` | 6 | **PASSED** |
| `tests/test_foundation.py` | 1 | **PASSED** |
