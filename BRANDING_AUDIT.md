# Astraea MT5 — Branding Audit Report

This document classifies all references to the legacy project name (`Kronos`) found across the repository into **Product Branding** (rebranded), **Technical Implementation** (retained for compatibility), and **Legal / Attribution** (retained).

## Reference Classification Audit

| Old Reference | File Location | Type | Action | Justification |
|---|---|---|---|---|
| `Kronos` | `README.md` | Product Branding | Replaced | Rebranded to Astraea MT5 |
| `Kronos Financial Prediction` | `webui/templates/index.html` | UI Branding | Replaced | Rebranded to Astraea MT5 |
| `Kronos Web UI` | `webui/app.py` | UI Logging | Replaced | Rebranded to Astraea MT5 |
| `Kronos` | `config/config.yaml` | System Configuration | Replaced | Rebranded application config labels |
| `Kronos` | `trading/models.py` | Application Schemas | Replaced | Rebranded application docstrings |
| `Kronos` / `KronosTokenizer` / `KronosPredictor` | `model/kronos.py` | Technical Class | Retained | Core neural network model classes; required for PyTorch/HF checkpoint compatibility |
| `KronosTokenizer` / `KronosPredictor` | `model/__init__.py` | Technical Exports | Retained | Core model API exports |
| `NeoQuasar/Kronos-small` | `config/config.yaml` | Model Identifier | Retained | Hugging Face Hub model weight identifier |
| `NeoQuasar/Kronos-Tokenizer-base` | `config/config.yaml` | Tokenizer Identifier | Retained | Hugging Face Hub tokenizer weight identifier |
| `Kronos` | `LICENSE` | Legal / License | Retained | MIT License legal copyright notice |
| `Kronos` | `README.md` (Attribution) | Attribution | Retained | Explicit attribution to underlying foundation model paper/authors |
