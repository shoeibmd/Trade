# Astraea MT5 — Data Flow & Algorithms

**1. Closed-Candle Extraction Pipeline**
- MT5 rates fetched starting at `start_pos = 1` to bypass active forming bar (position 0).
- Input context window padded to 400 closed candles.

**2. Forecast Generation & Caching Algorithm**
- Input DataFrame OHLCV + timestamps + params hashed via SHA-256.
- Bounded LRU cache (`max_cache_entries: 256`) returns cached `PredictionResult` in `<0.0001s` on hit.
- Cache miss triggers Kronos model autoregressive rollout.

**3. 100-Point Probabilistic Signal Engine Algorithm**
- **Forecast Score (0 to 50 pts)**: Directional magnitude of predicted close relative to current close.
- **Trend Filter (0 to 30 pts)**: Alignment across EMA 20, 50, and 200.
- **Momentum Filter (0 to 20 pts)**: RSI oversold (<30) / overbought (>70) confirmation.
- **Threshold**: Total Score $\ge 60$ required to issue `BUY` / `SELL` signal.

**4. Risk Sizing & Lot Calculation Math**
- $\text{Risk Amount} = \text{Account Equity} \times \text{Risk Percent}$.
- $\text{Lot Size} = \frac{\text{Risk Amount}}{\text{SL Distance in Pips} \times \text{Pip Value per Lot}}$.
- Dynamic clipping against broker `min_volume`, `max_volume`, and `volume_step`.
