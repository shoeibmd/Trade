# Astraea MT5 — Windows Demo-Terminal Validation & Gateway Guide

**Date**: October 6, 2026
**Application**: Astraea MT5 — AI-Powered Forex Trading Intelligence (`astraea_mt5`)
**Status**: `PENDING_WINDOWS_TERMINAL` (Validation pending live Windows MT5 execution)

---

## 1. Environment & Prerequisites

To validate **Astraea MT5** on a Windows host with a live MetaTrader 5 terminal:

1. **Operating System**: Windows 10/11 (64-bit) or Windows Server 2019/2022.
2. **Python**: Python 3.10+ (64-bit).
3. **MetaTrader 5 Terminal**: Installed from your broker (e.g. MetaQuotes / IC Markets / Forex.com).
4. **Broker Demo Account**: Active MT5 Demo login, password, and server address.

---

## 2. Windows Environment Setup

### Step 1: Install Python Dependencies
Open PowerShell or Command Prompt in the repository root:

```cmd
pip install -r requirements.txt
pip install MetaTrader5
```

### Step 2: Configure Environment Variables
Create a local `.env` file (do not commit credentials to git):

```env
# System Safety Control
SYSTEM_MODE=PAPER
LIVE_TRADING_ENABLED=false

# MT5 Terminal Credentials (Placeholder Values)
MT5_MODE=NATIVE
MT5_LOGIN=12345678
MT5_PASSWORD=your_demo_password_here
MT5_SERVER=Broker-Demo
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

---

## 3. Read-Only Connectivity Validation Procedure

Execute the following test steps in Windows PowerShell to verify read-only integration:

### Test 1: Native Terminal & Account Verification
Run Python interactive shell or validation script:

```python
from trading.mt5_connection import MT5Connection

conn = MT5Connection(mode="NATIVE")
ok, msg = conn.initialize()
print("Initialization:", ok, msg)

ok_login, msg_login = conn.connect()
print("Connection:", ok_login, msg_login)

terminal_info = conn.get_terminal_info()
print("Terminal Info:", terminal_info)

account_info = conn.get_account_info()
print("Account Info (Balance/Equity):", account_info.get("balance"), account_info.get("equity"))
```

### Test 2: Symbol Availability & M5 Rate Fetching
Verify symbol support and historical candle integrity without modifying positions:

```python
from trading.mt5_data import MT5DataEngine

engine = MT5DataEngine()
ok_sym = conn.check_symbol("EURUSD")
print("EURUSD Symbol Visible:", ok_sym)

df = engine.get_rates_from_pos("EURUSD", "M5", count=520)
print("Fetched Candles Count:", len(df))
print("Data Head:\n", df.head(2))
print("Data Tail (Closed Candles):\n", df.tail(2))
```

### Test 3: Handoff to Kronos Foundation Model
Verify rate DataFrame handoff to the foundation forecasting adapter:

```python
from trading.kronos_adapter import KronosAdapter

adapter = KronosAdapter(lookback=400, pred_len=120)
pred_res, err = adapter.predict_forecast(df, symbol="EURUSD", timeframe="M5")
print("Forecast Status:", "Success" if pred_res else err)
print("Predicted Close Count:", len(pred_res.predicted_close) if pred_res else 0)
```

---

## 4. Linux / Docker Gateway Client Setup

When running Astraea MT5 inside a Linux container or remote cloud instance:

1. **Windows Gateway Server**: Run a lightweight Windows REST proxy wrapping `MetaTrader5` listening on port `8080`.
2. **Authentication**: Enforce `X-MT5-API-Key` headers on every endpoint.
3. **Linux Client Config (`.env`)**:

```env
SYSTEM_MODE=PAPER
LIVE_TRADING_ENABLED=false
MT5_MODE=GATEWAY
MT5_GATEWAY_URL=http://<windows-host-ip>:8080
MT5_GATEWAY_API_KEY=your_secure_gateway_key
```

4. **Security & Firewalls**: Restrict port `8080` access via IP whitelisting or Windows Firewall.

---

## 5. Validation Checklist

- [ ] Terminal Initialized (`ConnectionState.INITIALIZED`)
- [ ] Demo Account Connected (`ConnectionState.CONNECTED`)
- [ ] `EURUSD` Symbol Available in Market Watch
- [ ] 520 Closed M5 Candles Retrieved
- [ ] Timestamps Monotonically Increasing (Zero NaN / Duplicates)
- [ ] 120-step Forecast Produced by Kronos Adapter
- [ ] `system.mode: PAPER` Enforced
- [ ] `live_trading_enabled: false` Enforced

*Actual validation status remains `PENDING_WINDOWS_TERMINAL` until executed against Windows hardware.*
