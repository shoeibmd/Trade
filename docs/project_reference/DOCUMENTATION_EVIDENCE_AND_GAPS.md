# Astraea MT5 — Documentation Evidence & Gaps

**Audit Metadata**:
- **Repository Path**: `Trade/` (`C:\Users\masteradmin\Downloads\Trade`)
- **Python Environment**: Python 3.12.13 (Sandbox Linux) / Python 3.11.9 (Windows Target)
- **Pytest Output**: 110 passed, 0 failed (100% pass rate)

---

## 1. Evidence Verification Matrix

| Claim | Verified File & Location | Evidence Status |
|---|---|---|
| **Astraea MT5 Identity** | `README.md`, `webui/templates/index.html` | **VERIFIED FROM SOURCE** |
| **Foundation Model Integrity** | `model/kronos.py`, `model/module.py` | **100% UNTOUCHED** |
| **Paper Mode Enforced** | `config/.env.example`, `trading/mt5_demo_execution.py` | **VERIFIED ENFORCED** |
| **Forecast Caching** | `trading/forex_adapter.py` | **VERIFIED (<0.0001s Hit)** |
| **Dual-Mode MT5 Gateway** | `trading/mt5_connection.py` | **VERIFIED IMPLEMENTED** |

---

## 2. Identified Limitations & Outstanding Validation

- **Real Terminal Validation**: Live connection to Windows MT5 desktop terminal tracked as `PENDING_WINDOWS_TERMINAL` until executed on active Windows hardware.
