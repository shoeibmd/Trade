# Astraea MT5 — Branding Changelog

## Summary of Rebranding Changes

- **Old Identity**: Kronos / Kronos Trading System
- **New Identity**: **Astraea MT5** (Short Name: **Astraea**, Tech ID: `astraea_mt5`)
- **Tagline**: **AI-Powered Forex Trading Intelligence**

---

## Modifed & Added Files

1. **`README.md`**:
   - Completely rewritten to introduce Astraea MT5.
   - Updated architecture flowchart (Mermaid) to reflect Astraea MT5 pipeline.
   - Added explicit attribution to underlying Kronos time series foundation model.

2. **`assets/branding/`**:
   - Created `logo.svg` (Horizontal dark background vector logo).
   - Created `logo-dark.svg` (Dark mode logo).
   - Created `logo-light.svg` (Light mode logo).
   - Created `logo-icon.svg` (App icon).
   - Created `favicon.svg` (32x32 browser favicon).
   - Created `BRAND_GUIDELINES.md` & `README.md`.

3. **`webui/templates/index.html` & `webui/app.py`**:
   - Updated Web Dashboard titles, headers, and color scheme to Astraea dark fintech palette (`#0B132B`, `#00F0FF`, `#7000FF`).
   - Ensured all visible text is 100% in English.

4. **`BRAND_GUIDELINES.md`**:
   - Created root brand guidelines covering visual identity, color tokens, and font stacks.

5. **`BRANDING_AUDIT.md`**:
   - Documented exact classifications for all retained technical model names (`KronosPredictor`, `KronosTokenizer`) and legal attributions.

6. **`BRANDING_ASSETS_TODO.md`**:
   - Documented optional raster asset tracking.

7. **`ASTRAEA_MT5_PRODUCT_IDENTITY.md`**:
   - Complete product identity reference.

8. **`PHASE_BRANDING_REPORT.md`**:
   - Complete execution and verification report for the Rebranding Phase.

---

## Technical Identifiers Intentionally Retained

To guarantee zero regression in the underlying AI forecasting engine:
- `model/kronos.py`: `KronosTokenizer`, `Kronos`, `KronosPredictor` class names are untouched.
- `model/module.py`: `BSQuantizer`, `TransformerBlock` and related layers are untouched.
- `model/__init__.py`: Package exports are untouched.
- `tests/test_kronos_regression.py`: Regression test cases are untouched.
