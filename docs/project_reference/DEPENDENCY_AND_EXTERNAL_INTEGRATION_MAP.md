# Astraea MT5 — Dependency & Integration Map

## 1. Core Python Dependencies (`requirements.txt`)

- `torch>=2.0.0`: Autoregressive Transformer neural network framework.
- `numpy`: Numerical matrix operations.
- `pandas==2.2.2`: Time-series OHLCV DataFrame manipulation.
- `einops==0.8.1`: Tensor reshaping for MultiHeadAttention.
- `huggingface_hub==0.33.1`: Pretrained model weight downloading.
- `safetensors==0.6.2`: Safe model tensor weight loading.
- `Flask`: Dashboard REST backend server.
- `flask-cors`: Cross-Origin Resource Sharing support.
- `plotly`: Financial K-line candlestick chart rendering.
- `PyYAML`: Configuration YAML parsing.
- `requests`: HTTP client for Linux MT5 Gateway Client.
- `pytest`: Automated test runner framework.

## 2. Optional Dependencies

- `MetaTrader5`: Native Python API for MetaTrader 5 (Windows only).
