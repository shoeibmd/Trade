# Astraea MT5 — Configuration & Environment

**Environment Variables Template (`config/.env.example`)**:

```env
# System Configuration
SYSTEM_MODE=PAPER
LIVE_TRADING_ENABLED=false

# MT5 Terminal & Gateway Settings
MT5_MODE=GATEWAY # GATEWAY on Linux/Docker, NATIVE on Windows
MT5_LOGIN=12345678
MT5_PASSWORD=your_demo_password
MT5_SERVER=Broker-Demo
MT5_GATEWAY_URL=http://localhost:8080
MT5_GATEWAY_API_KEY=your_secure_api_key

# Forecasting Settings
KRONOS_MODEL_NAME=NeoQuasar/Kronos-small
KRONOS_TOKENIZER_NAME=NeoQuasar/Kronos-Tokenizer-base
KRONOS_DEVICE=cpu
KRONOS_MAX_CONTEXT=512
KRONOS_LOOKBACK=400
KRONOS_PRED_LEN=120
```
