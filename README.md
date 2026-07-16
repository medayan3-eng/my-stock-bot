# Murphy Screener

A stock **screener** (not an auto-trader). It scans a universe of stocks, scores each one 0-100
using John Murphy's technical/intermarket principles plus candlestick confirmation, and explains
in plain English why it scored that way. You decide what to trade.

## Files
| File | Purpose |
|---|---|
| `murphy_screener.py` | Core engine — data fetching, indicators, scoring logic, and the full S&P 500 ticker/sector list (embedded directly in the code, not an external file). Also runnable as a CLI. |
| `dashboard_app.py` | Streamlit web UI. **This is the Streamlit Cloud main module.** |
| `requirements.txt` | Python dependencies for deployment. |

Both Python files must live in the **same folder** (repo root, or the same subfolder) — the dashboard
imports `murphy_screener.py` directly. The S&P 500 list is embedded in code specifically so nothing
breaks if a data file goes missing or the working directory changes on deployment.

## Run locally
```
pip install -r requirements.txt
streamlit run dashboard_app.py
```

## Run as a CLI (no browser UI)
```
python murphy_screener.py                     # scans the full embedded S&P 500 list
python murphy_screener.py AAPL MSFT NVDA       # scans just these tickers
python murphy_screener.py --file mylist.txt    # one ticker per line
python murphy_screener.py --top 20             # show only top 20 by score
```

In the dashboard, the sidebar lets you pick **Manual list**, an **S&P 500 subset** (choose any count
from 1 up to the full ~505 tickers with a slider), or the **Full S&P 500**.

## Deploy on Streamlit Cloud
1. Push all three files (`murphy_screener.py`, `dashboard_app.py`, `requirements.txt`) to your GitHub
   repo (root of the `main` branch).
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
- The embedded S&P 500 list (in `murphy_screener.py`, the `SP500_DATA` dict) is a static snapshot;
  some tickers may have since been added/removed from the index. Edit that dict directly, or pass
  your own list with `--file` / the manual-list mode in the dashboard.
- This is a research/screening tool, not investment advice. All trading decisions are yours.
- Tune weights/thresholds (e.g. `VOLUME_SPIKE_MULT`, `NEAR_MA50_PCT`) at the top of `murphy_screener.py`.
