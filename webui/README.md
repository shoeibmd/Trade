# Astraea MT5 Web UI

Web user interface for **Astraea MT5 — AI-Powered Forex Trading Intelligence**, providing an intuitive graphical dashboard for MT5 Forex forecasting and monitoring.

> **Note**: Astraea MT5 is the trading application interface. It utilizes the underlying Kronos foundation forecasting model (`Kronos`, `KronosTokenizer`, `KronosPredictor`) for time-series forecasting.

## ✨ Features

- **Multi-format data support**: Supports CSV, Feather and MT5 market streaming rate structures
- **Smart time window**: Fixed 400+120 data point time window slider selection
- **Foundation model forecasting**: Integrated Kronos foundation models (mini, small, base)
- **Prediction quality control**: Adjustable temperature, nucleus sampling, sample count and other parameters
- **Multi-device support**: Supports CPU, CUDA, MPS and other computing devices
- **Comparison analysis**: Detailed comparison between prediction results and actual market data
- **K-line chart display**: Professional financial K-line chart display using Plotly

## 🚀 Quick Start

### Method 1: Start with Python script
```bash
cd webui
python run.py
```

### Method 2: Start with Shell script
```bash
cd webui
chmod +x start.sh
./start.sh
```

### Method 3: Start Flask application directly
```bash
cd webui
python app.py
```

After successful startup, visit http://localhost:7070 (or http://localhost:5000 if configured)

## 📋 Usage Steps

1. **Load data**: Select financial/Forex data file from data directory
2. **Load model**: Select Kronos foundation model and computing device
3. **Set parameters**: Adjust prediction quality parameters
4. **Select time window**: Use slider to select 400+120 data point time range
5. **Start prediction**: Click prediction button to generate results
6. **View results**: View prediction results in charts and tables

## 🤖 Model Support

- **Kronos-mini**: 4.1M parameters, lightweight fast prediction
- **Kronos-small**: 24.7M parameters, balanced performance and speed
- **Kronos-base**: 102.3M parameters, high quality prediction

## 📄 License

This project follows the license terms of the original Kronos project (MIT License).
