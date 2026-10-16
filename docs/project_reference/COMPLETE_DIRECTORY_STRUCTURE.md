# Astraea MT5 — Complete Directory Structure

```text
Trade/
├── README.md                           # Main application documentation
├── requirements.txt                    # Python package dependencies
├── BRANDING_AUDIT.md                   # Rebranding audit report
├── ASTRAEA_READINESS_AUDIT.md          # Readiness audit findings
├── WINDOWS_MT5_VALIDATION_GUIDE.md     # Windows MT5 & Gateway validation guide
├── PHASE_15_MT5_CONNECTIVITY_REPORT.md # MT5 connectivity phase report
│
├── assets/                             # Product Branding & Visual Assets
│   └── branding/
│       ├── logo.svg                    # Vector logo banner (380px max-width)
│       └── astraea_logo.png            # PNG fallback logo asset
│
├── config/                             # Environment & System Configurations
│   └── .env.example                    # Template environment variables
│
├── docs/                               # Project Documentation
│   └── project_reference/              # Complete 16-document audit reference package
│
├── model/                              # UNTOUCHED Foundation Forecasting Library
│   ├── __init__.py                     # Model exports (Kronos, KronosTokenizer, KronosPredictor)
│   ├── kronos.py                       # Autoregressive Transformer & Tokenizer classes
│   └── module.py                       # Neural network layers (BSQuantizer, RoPE, RMSNorm)
│
├── trading/                            # Astraea MT5 Trading System Architecture
│   ├── __init__.py                     # Exports AstraeaForecastingEngine & models
│   ├── models.py                       # Data classes (TickData, BarData, TradingSignal, Position, SignalType)
│   ├── mt5_connection.py               # Dual-mode MT5 Connector (Native / Gateway Client)
│   ├── mt5_data.py                     # Market Data Engine & bar validation rules
│   ├── forex_adapter.py                # AstraeaForecastingEngine & KronosAdapter
│   ├── kronos_adapter.py               # Re-export module for backward compatibility
│   ├── indicators.py                   # Technical Indicator Engine (ATR, RSI, EMA, Bollinger)
│   ├── signal_engine.py                # 100-Point Probabilistic Signal Engine
│   ├── risk_manager.py                 # Forex Risk Manager & Lot Sizer
│   ├── paper_execution.py              # Paper Execution Engine & PnL simulator
│   ├── backtester.py                   # Forex Backtester Engine
│   ├── walk_forward.py                 # Walk-Forward Out-of-Sample Engine
│   ├── mt5_demo_execution.py           # MT5 Execution Engine with 9 Safety Gates
│   ├── position_manager.py             # Active Position Manager & Trailing Stop
│   └── strategy_optimizer.py          # Strategy Parameter Grid-Search Optimizer
│
├── webui/                              # Analytics & Monitoring Web Dashboard
│   ├── app.py                          # Flask web server backend
│   ├── README.md                       # Dashboard documentation
│   ├── templates/
│   │   └── index.html                  # HTML/CSS/Plotly SPA interface
│   └── prediction_results/             # Saved prediction JSON outputs
│
└── tests/                              # Comprehensive Test Suite (109 Tests)
    ├── test_kronos_regression.py      # Baseline foundation model regression checks
    ├── test_forex_adapter.py           # Forex adapter & forecast cache tests
    ├── test_mt5_connection.py          # MT5 connection & gateway client tests
    ├── test_mt5_data.py                # Market data validation & tick volume tests
    ├── test_indicators.py              # Technical indicator calculation tests
    ├── test_signal_engine.py           # Signal scoring & threshold tests
    ├── test_risk_manager.py            # Risk sizing & daily loss limit tests
    ├── test_paper_execution.py         # Paper execution & PnL formula tests
    ├── test_backtester.py              # Backtesting & anti-look-ahead tests
    ├── test_walk_forward.py            # Walk-forward optimization tests
    ├── test_strategy_optimizer.py       # Strategy optimizer & reproducibility tests
    ├── test_mt5_demo_execution.py      # Demo execution & safety gate tests
    ├── test_position_manager.py        # Position manager & trailing stop tests
    └── test_dashboard.py               # Dashboard API & UI route tests
```
