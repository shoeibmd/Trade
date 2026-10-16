# Astraea MT5 — Security & Trading Safety

## 1. Non-Bypassable System Safety Controls

1. **System Mode Default**: `system.mode: PAPER`.
2. **Live Trading Enablement**: `live_trading_enabled: false`.
3. **Real Account Protection Gate**: In `trading/mt5_demo_execution.py`, any account identified as `ACCOUNT_TRADE_MODE_REAL` triggers an immediate hard exception, blocking order execution completely regardless of configuration overrides.
4. **Credential Privacy**: Passwords and API keys are read from environment variables or `config/.env` and are strictly excluded from logging statements.

## 2. Risk Controls

- Daily Loss Limits: Automatic trade rejection when equity drawdown reaches configured maximum.
- Lot Sizing Safeguards: Bounded against broker minimum, maximum, and lot step size constraints.
