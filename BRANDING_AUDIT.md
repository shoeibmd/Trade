# Astraea MT5 — Branding Audit & Verification Report

**Date**: October 6, 2026
**Application Name**: Astraea MT5 — AI-Powered Forex Trading Intelligence
**Short Name**: Astraea
**Technical ID**: `astraea_mt5`
**Underlying Model**: Kronos Foundation Model (`Kronos`, `KronosTokenizer`, `KronosPredictor`)

---

## 1. Executive Summary

A comprehensive repository-wide rebranding audit was conducted to establish **Astraea MT5** as the primary user-facing trading application while maintaining full upstream attribution and technical integrity of the underlying **Kronos** foundation forecasting model.

All modifications preserve:
- `model/kronos.py`, `model/module.py`, `model/__init__.py`
- Pretrained model class structures (`Kronos`, `KronosTokenizer`, `KronosPredictor`)
- Hugging Face model identifiers (`NeoQuasar/Kronos-small`, `NeoQuasar/Kronos-base`, etc.)
- Paper citations and upstream MIT License
- Safe system settings (`live_trading_enabled: false`, `system.mode: PAPER`)

---

## 2. Updated Files Summary

| File | Purpose | User-Facing Rebranding Applied |
|---|---|---|
| `README.md` | Primary Application README | Updated main heading, badge titles, product overview, setup guide, and explicit model attribution notice. |
| `webui/templates/index.html` | Web Dashboard HTML Interface | Updated page title, header, subtitle, logo reference, and console logs. |
| `webui/app.py` | Web Dashboard Backend | Added branding asset route, updated chart titles and startup logs. |
| `webui/README.md` | Web UI Documentation | Rebranded to Astraea MT5 Web UI with explicit Kronos foundation model notes. |
| `assets/branding/astraea_logo.png` | Product Logo Asset | Added Astraea MT5 logo asset for web dashboard and documentation. |

---

## 3. Preserved Technical Kronos References

The following technical references were intentionally preserved to ensure zero breakage of model loading, inference pipelines, and automated test suites:

1. **Core Model Source Files**:
   - `model/kronos.py`
   - `model/module.py`
   - `model/__init__.py`

2. **Python Classes & Functions**:
   - `Kronos`
   - `KronosTokenizer`
   - `KronosPredictor`
   - `auto_regressive_inference`
   - `get_model_class`

3. **Hugging Face Checkpoint Identifiers**:
   - `NeoQuasar/Kronos-mini`
   - `NeoQuasar/Kronos-small`
   - `NeoQuasar/Kronos-base`
   - `NeoQuasar/Kronos-Tokenizer-base`
   - `NeoQuasar/Kronos-Tokenizer-2k`

4. **Upstream Research & Legal Attribution**:
   - Paper citation: `Kronos: A Foundation Model for the Language of Financial Markets` (Shi et al., AAAI 2026 / arXiv 2508.02739).
   - MIT License headers and original copyright attributions.

---

## 4. Test & Safety Verification

- **Test Suite Executed**: `python /tmp/run_all_tests.py` / `pytest tests/test_kronos_regression.py`
- **Result**: 4 passed, 0 failed.
- **Safety Flags**:
  - `system.mode`: `PAPER`
  - `live_trading_enabled`: `false`

---

*End of Branding Audit Report.*
