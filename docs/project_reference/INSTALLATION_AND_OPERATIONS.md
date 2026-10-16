# Astraea MT5 — Installation & Operations

## Windows Setup

```powershell
Set-Location "C:\Users\masteradmin\Downloads\Trade"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install MetaTrader5
```

## Running the Application & Web UI

```powershell
python webui/app.py
```

Open browser at `http://localhost:7070`.

## Running Test Suite

```powershell
pytest tests/ -v
```
