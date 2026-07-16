# Murphy Screener

A **screener** (not an auto-trader). It scans a universe of stocks and/or ETFs, scores each one
0-100 using John Murphy's technical/intermarket principles plus candlestick confirmation, and
explains in plain English why it scored that way. You decide what to trade.

## Files
| File | Purpose |
|---|---|
| `murphy_screener.py` | Core engine — data fetching, indicators, scoring logic. Also runnable as a CLI. |
| `sp_universe_data.py` | Embedded S&P 500 / S&P 400 / S&P 600 ticker → (name, sector) data. |
| `dashboard_app.py` | Streamlit web UI. **This is the Streamlit Cloud main module.** |
| `requirements.txt` | Python dependencies for deployment. |

All Python files must live in the **same folder** (repo root, or the same subfolder) — the dashboard
imports `murphy_screener.py`, which in turn imports `sp_universe_data.py`. Nothing is loaded from an
external CSV/PDF at run time, so there's no dependency on a data file surviving deployment.

## Run locally
```
pip install -r requirements.txt
streamlit run dashboard_app.py
```

## Run as a CLI (no browser UI)
```
python murphy_screener.py                              # scans the full S&P 500 (default universe)
python murphy_screener.py --universe sp400              # scans the full S&P 400 (mid-cap)
python murphy_screener.py --universe all --count 200    # first 200 tickers across 500+400+600 combined
python murphy_screener.py AAPL MSFT NVDA SPY XLK         # scans just these tickers (stocks + ETFs)
python murphy_screener.py --file mylist.txt              # one ticker per line
python murphy_screener.py --top 20                       # show only top 20 per list (stocks / ETFs)
```
The CLI (and the dashboard) automatically separates results into **two ranked lists — Stocks and
ETFs** — and saves them to separate CSVs (`screener_results_stocks.csv` / `screener_results_etfs.csv`).

## Universe coverage
- **S&P 500** — large-cap
- **S&P 400** — mid-cap
- **S&P 600** — small-cap
- **All combined** — all three merged (~1,500 tickers)

In the dashboard, pick an index and use the slider to scan any count from 1 up to the full size of
that universe, or switch to "Manual list" to type your own tickers (stocks and ETFs both work —
ETFs are auto-detected and routed to the ETF list).

## Deploy on Streamlit Cloud
1. Push all four files to your GitHub repo (root of the `main` branch).
2. In Streamlit Cloud app settings, set **Main file path** to `dashboard_app.py`.
3. Streamlit installs `requirements.txt` automatically and deploys.

## Scoring breakdown (0–100 for stocks; ETFs are scored out of 85 and rescaled to 100, since
sector-leadership and macro-regime alignment don't apply to a fund)
| Component | Points | Based on |
|---|---|---|
| 52-week uptrend + above 50/200 MA | up to 25 | *Technical Analysis of the Financial Markets* |
| Hugging the 50-MA on elevated volume (pullback opportunity) | up to 10 | same |
| Bollinger Band setup (squeeze / lower-band touch in an uptrend) | up to 10 | same |
| Bullish candlestick (Hammer, Engulfing, Piercing Line, Morning Star) | 10 | *Japanese Candlestick Charting Techniques* |
| Unusual trading volume (institutional money flow) | up to 10 | *Technical Analysis of the Financial Markets* |
| RSI | up to 10 | same |
| MACD | up to 10 | same |
| Sector relative strength (1w/1m/3m/12m vs. SPY) — stocks only | up to 10 | *Intermarket Analysis* |
| Alignment with the current intermarket regime (inflation/deflation) — stocks only | 5 | *Intermarket Analysis* |

Every ticker also gets a **stop-loss** (below the nearest support / 50-MA, whichever is lower) and a
**price target** (roughly a 2.5x reward-to-risk multiple, or the 52-week high if higher). Price,
stop-loss, target and R:R are always displayed to 2 decimal places.

## Sector strength / weakness summary
After building the sector relative-strength leaderboard (1w/1m/3m/12m vs. SPY, per Murphy's
intermarket-analysis / relative-strength approach), the scan prints two lists:
- **Sectors showing strength** — top third of the leaderboard
- **Sectors showing weakness** — bottom third

Use this to decide where to focus your scan before drilling into individual names.

## Notes
- The app fetches live data via `yfinance` — it needs internet access at run time.
- The embedded S&P 500/400/600 lists (in `sp_universe_data.py`) are static snapshots; some tickers
  may have since been added/removed from an index. Edit that file directly, or pass your own list
  with `--file` / the manual-list mode in the dashboard.
- ETF classification: any ticker in the embedded S&P 500/400/600 data is treated as a stock. Anything
  else is checked against a built-in list of common ETFs (SPY, QQQ, sector SPDRs, GLD, TLT, etc.);
  if still unmatched, a live yfinance lookup checks the `quoteType`.
- This is a research/screening tool, not investment advice. All trading decisions are yours.
