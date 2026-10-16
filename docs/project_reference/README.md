# Astraea MT5 — AI-Powered Forex Trading Intelligence

**Documentation Reference Index & System Overview**

---

## 📌 Project Overview

**Astraea MT5** is an enterprise-grade AI-powered MetaTrader 5 (MT5) Forex trading intelligence platform. It integrates real-time MT5 tick and bar streaming data, technical indicators, probabilistic 100-point signal scoring, dynamic risk management, paper execution, historical backtesting, walk-forward testing, position management, and an interactive Flask/Plotly web dashboard.

> **Forecasting Engine Notice**: Astraea MT5 uses its integrated foundation forecasting engine (`Kronos`, `KronosTokenizer`, `KronosPredictor`) to generate time-series price and volume predictions.

---

## 📚 Complete Project Reference Documentation

All detailed architectural, technical, operational, and auditing documents are located in `docs/project_reference/`:

1. [Project Overview & Main Guide](./README.md)
2. [Project Purpose & Requirements](./PROJECT_PURPOSE_AND_REQUIREMENTS.md)
3. [Complete Directory Structure](./COMPLETE_DIRECTORY_STRUCTURE.md)
4. [File-by-File Reference](./FILE_BY_FILE_REFERENCE.md)
5. [System Architecture](./SYSTEM_ARCHITECTURE.md)
6. [Data Flow & Algorithms](./DATA_FLOW_AND_ALGORITHMS.md)
7. [Configuration & Environment](./CONFIGURATION_AND_ENVIRONMENT.md)
8. [Installation & Operations](./INSTALLATION_AND_OPERATIONS.md)
9. [API & Dashboard Reference](./API_AND_DASHBOARD_REFERENCE.md)
10. [Testing & Verification Report](./TESTING_AND_VERIFICATION.md)
11. [Security & Trading Safety](./SECURITY_AND_TRADING_SAFETY.md)
12. [Dependency & Integration Map](./DEPENDENCY_AND_EXTERNAL_INTEGRATION_MAP.md)
13. [Implementation Status & Roadmap](./IMPLEMENTATION_STATUS_AND_ROADMAP.md)
14. [Troubleshooting Guide](./TROUBLESHOOTING.md)
15. [Glossary of Terms](./GLOSSARY.md)
16. [Documentation Evidence & Gaps](./DOCUMENTATION_EVIDENCE_AND_GAPS.md)

---

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Launching the Dashboard

```bash
python webui/app.py
```

### Running Tests

```bash
pytest tests/ -v
```

---

## 🛡️ Safety Configuration

- Default System Mode: `system.mode: PAPER`
- Live Trading Override: `live_trading_enabled: false`
