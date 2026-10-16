# Astraea MT5 — Glossary of Terms

- **Astraea MT5**: AI-Powered Forex Trading Intelligence platform (`astraea_mt5`).
- **Kronos**: Pretrained autoregressive foundation model family (`Kronos`, `KronosTokenizer`, `KronosPredictor`) used as the time-series forecasting component.
- **Closed-Candle Guarantee**: Rate retrieval logic bypassing the active unclosed bar (`start_pos = 1`) to eliminate look-ahead bias.
- **Signal Score**: 100-point probabilistic score combining forecast direction (0-50 pts), trend EMA alignment (0-30 pts), and RSI momentum (0-20 pts).
- **Paper Execution**: Simulated order filling and PnL calculation enforced when `system.mode = PAPER`.
- **MT5GatewayClient**: REST/JSON gateway client enabling Linux/Docker containers to connect securely to Windows-hosted MT5 terminals using `X-MT5-API-Key` authentication.
