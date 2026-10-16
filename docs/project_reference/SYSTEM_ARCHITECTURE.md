# Astraea MT5 — System Architecture

```
┌────────────────────────────────────────────────────────┐
│                   METATRADER 5 TERMINAL                 │
│         (Windows Native Terminal or Gateway Proxy)     │
└───────────────────────────┬────────────────────────────┘
                            │ (Closed Rate Data)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   MT5 DATA ENGINE                      │
│        (Bar Data Validation & History Checks)          │
└───────────────────────────┬────────────────────────────┘
                            │ (Validated Bar DataFrame)
                            ▼
┌────────────────────────────────────────────────────────┐
│             ASTRAEA FORECASTING ENGINE                 │
│         (KronosAdapter with SHA-256 Caching)           │
└───────────────────────────┬────────────────────────────┘
                            │ (PredictionResult)
                            ▼
┌────────────────────────────────────────────────────────┐
│             TECHNICAL INDICATOR ENGINE                 │
│         (ATR, RSI, EMA, Bollinger Bands)              │
└───────────────────────────┬────────────────────────────┘
                            │ (Indicator Features)
                            ▼
┌────────────────────────────────────────────────────────┐
│               100-POINT SIGNAL ENGINE                  │
│       (Directional Scoring & Target Calculation)       │
└───────────────────────────┬────────────────────────────┘
                            │ (TradingSignal)
                            ▼
┌────────────────────────────────────────────────────────┐
│                  FOREX RISK MANAGER                    │
│      (Equity Sizing, Pip Math & Daily Loss Limits)     │
└───────────────────────────┬────────────────────────────┘
                            │ (Approved Risk Decision)
                            ▼
┌────────────────────────────────────────────────────────┐
│               PAPER EXECUTION ENGINE                   │
│        (PAPER Mode Enforcement & PnL Tracking)         │
└───────────────────────────┬────────────────────────────┘
                            │ (Position Updates)
                            ▼
┌────────────────────────────────────────────────────────┐
│               WEB UI DASHBOARD / API                   │
│          (Flask Backend & Interactive Plotly UI)       │
└────────────────────────────────────────────────────────┘
```
