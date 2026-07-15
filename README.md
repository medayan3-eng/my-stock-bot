# Murphy Screener

A stock **screener** (not an auto-trader). It scans a universe of stocks, scores each one 0-100
using John Murphy's technical/intermarket principles plus candlestick confirmation, and explains
in plain English why it scored that way. You decide what to trade.

## Files
| File | Purpose |
|---|---|
| `murphy_screener.py` | Core engine — data fetching, indicators, scoring logic. Also runnable as a CLI. |
| `dashboard_app.py` | Streamlit web UI. **This is the Streamlit Cloud main module.** |
| `sp500_tickers.csv` | Bundled S&P 500 ticker + sector list (used instead of a live Wikipedia scrape). |
| `requirements.txt` | Python dependencies for deployment. |

All four files must live in the **same folder** (repo root, or the same subfolder) — the dashboard
imports `murphy_screener.py` directly and both scripts load `sp500_tickers.csv` from their own folder.

## Run locally
```
pip install -r requirements.txt
streamlit run dashboard_app.py
```

## Run as a CLI (no browser UI)
```
python murphy_screener.py                     # scans the full bundled S&P 500 list
python murphy_screener.py AAPL MSFT NVDA       # scans just these tickers
python murphy_screener.py --file mylist.txt    # one ticker per line
python murphy_screener.py --top 20             # show only top 20 by score
```

## Deploy on Streamlit Cloud
1. Push all four files to your GitHub repo (root of the `main` branch).
2. In Streamlit Cloud app settings, set **Main file path** to `dashboard_app.py`.
3. Streamlit installs `requirements.txt` automatically and deploys.

## Scoring breakdown (0–100)
| Component | Points | Based on |
|---|---|---|
| 52-week uptrend + above 50/200 MA | up to 25 | *Technical Analysis of the Financial Markets* |
| Hugging the 50-MA on elevated volume (pullback opportunity) | up to 10 | same |
| Bollinger Band setup (squeeze / lower-band touch in an uptrend) | up to 10 | same |
| Bullish candlestick (Hammer, Engulfing, Piercing Line, Morning Star) | 10 | *Japanese Candlestick Charting Techniques* |
| Unusual trading volume (institutional money flow) | up to 10 | *Technical Analysis of the Financial Markets* |
| RSI | up to 10 | same |
| MACD | up to 10 | same |
| Sector relative strength (1w/1m/3m/12m vs. SPY) | up to 10 | *Intermarket Analysis* |
| Alignment with the current intermarket regime (inflation/deflation) | 5 | *Intermarket Analysis* |

Every stock also gets a **stop-loss** (below the nearest support / 50-MA, whichever is lower) and a
**price target** (roughly a 2.5x reward-to-risk multiple, or the 52-week high if higher).

## Notes
- The app fetches live data via `yfinance` — it needs internet access at run time.
- The bundled `sp500_tickers.csv` is a static snapshot; some tickers may have since been added/removed
  from the index. Feel free to edit the CSV or pass your own list with `--file` / the manual-list mode.
- This is a research/screening tool, not investment advice. All trading decisions are yours.
- Tune weights/thresholds (e.g. `VOLUME_SPIKE_MULT`, `NEAR_MA50_PCT`) at the top of `murphy_screener.py`.
