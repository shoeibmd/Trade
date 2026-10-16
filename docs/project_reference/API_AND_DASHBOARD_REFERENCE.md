# Astraea MT5 — API & Dashboard Reference

## Web UI REST API Endpoints (`webui/app.py`)

- `GET /`: Serves single-page HTML interface (`webui/templates/index.html`).
- `GET /assets/branding/<filename>`: Serves product logos and visual branding assets.
- `GET /api/available-models`: Returns list of supported foundation model sizes (`kronos-mini`, `kronos-small`, `kronos-base`).
- `POST /api/load-model`: Loads requested model and tokenizer onto CPU/CUDA device.
- `GET /api/model-status`: Returns model initialization and device status.
- `GET /api/data-files`: Returns list of available K-line data CSV/Feather files in `data/`.
- `POST /api/load-data`: Loads and validates selected data file.
- `POST /api/predict`: Runs forecast inference via `KronosPredictor`, returns Plotly JSON chart and comparison metrics.
