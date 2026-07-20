"""
dashboard_app.py
Streamlit UI for the Murphy Screener.

Deploy this as your Streamlit Cloud main module. It needs
murphy_screener.py (and sp_universe_data.py, which murphy_screener.py
imports) in the SAME folder/repo.
"""

import streamlit as st
import pandas as pd

import murphy_screener as ms

st.set_page_config(page_title="Murphy Screener", page_icon="📈", layout="wide")

# ---------------------------------------------------------------------------
# THEME / STYLING
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(180deg, #0b1220 0%, #0f1b2d 100%);
    }

    /* Hero header */
    .hero {
        padding: 1.6rem 2rem;
        border-radius: 18px;
        background: linear-gradient(120deg, #1e3a5f 0%, #2b5876 45%, #4e4376 100%);
        box-shadow: 0 8px 30px rgba(0,0,0,0.35);
        margin-bottom: 1.6rem;
    }
    .hero h1 {
        color: #ffffff;
        font-weight: 800;
        font-size: 2.1rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .hero p {
        color: #cfe0f0;
        margin: 0.35rem 0 0 0;
        font-size: 1.02rem;
    }

    /* Section headers */
    .section-title {
        color: #f5f7fa;
        font-weight: 700;
        font-size: 1.25rem;
        margin: 1.4rem 0 0.6rem 0;
        border-left: 4px solid #4fc3f7;
        padding-left: 0.6rem;
    }

    /* Score badge */
    .badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.95rem;
        color: white;
    }
    .badge-high { background: linear-gradient(90deg, #11998e, #38ef7d); }
    .badge-mid  { background: linear-gradient(90deg, #f7971e, #ffd200); color:#1a1a1a; }
    .badge-low  { background: linear-gradient(90deg, #ec008c, #fc6767); }

    .sector-chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 8px;
        background: rgba(79, 195, 247, 0.15);
        color: #4fc3f7;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(79, 195, 247, 0.35);
    }

    .card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
    }

    .reason-item {
        color: #d7e3ee;
        font-size: 0.92rem;
        margin: 3px 0;
    }

    .pct-up { color: #38ef7d; font-weight: 700; }
    .pct-down { color: #fc6767; font-weight: 700; }

    div[data-testid="stMetricValue"] { color: #4fc3f7; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📈 Murphy Screener</h1>
        <p>A stock <b>screener</b> — not an auto-trader — built on trend, Bollinger Bands, candlesticks,
        volume, RSI/MACD, sector strength and Murphy's intermarket regime model. It scores each stock
        and explains why. You decide what to do with it.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def score_badge(score):
    if score >= 70:
        cls = "badge-high"
    elif score >= 45:
        cls = "badge-mid"
    else:
        cls = "badge-low"
    return f'<span class="badge {cls}">{score:.0f}</span>'


def pct_html(value):
    if value is None or value != value:  # NaN check
        return "n/a"
    cls = "pct-up" if value >= 0 else "pct-down"
    arrow = "▲" if value >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {value:+.2f}%</span>'


# ---------------------------------------------------------------------------
# Cached data fetchers (avoid re-hitting Yahoo Finance on every rerun)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def cached_regime():
    return ms.get_intermarket_regime()


@st.cache_data(ttl=300, show_spinner=False)
def cached_sector_leaderboard():
    return ms.get_sector_leaderboard()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_history(ticker):
    return ms.fetch_history(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_sector(ticker):
    return ms.get_sector(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_is_etf(ticker):
    return ms.is_etf(ticker)


# ---------------------------------------------------------------------------
# LIVE HOME SCREEN: intermarket regime + sector leaderboard
# (shown immediately, before any scan is run)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">🌍 Current Intermarket Regime</div>', unsafe_allow_html=True)
with st.spinner("Reading the intermarket regime (SPY / TLT / DBC / UUP)..."):
    regime = cached_regime()
st.markdown(f'<div class="card">{regime["description"]}</div>', unsafe_allow_html=True)
trend_cols = st.columns(4)
arrow_map = {"up": "🟢 Rising", "down": "🔴 Falling", "flat": "⚪ Flat", "unknown": "❓ Unknown"}
for col, (name, trend) in zip(trend_cols, regime["trends"].items()):
    col.metric(name, arrow_map.get(trend, trend))

st.markdown('<div class="section-title">🏭 Sector Leaderboard (vs. SPY)</div>', unsafe_allow_html=True)
with st.spinner("Building sector relative-strength leaderboard..."):
    sector_leaderboard = cached_sector_leaderboard()

strong_etfs = set()
if sector_leaderboard:
    lb_rows = []
    for etf, info in sorted(sector_leaderboard.items(), key=lambda kv: kv[1]["rank"]):
        lb_rows.append({
            "Rank": info["rank"], "Sector": info["sector"], "ETF": etf,
            "Price": info.get("price"),
            "Today %": info.get("day_change_pct"),
            "1w %": round(info["1w"], 2) if info["1w"] == info["1w"] else None,
            "1m %": round(info["1m"], 2) if info["1m"] == info["1m"] else None,
            "3m %": round(info["3m"], 2) if info["3m"] == info["3m"] else None,
            "12m %": round(info["12m"], 2) if info["12m"] == info["12m"] else None,
        })
    lb_df = pd.DataFrame(lb_rows)
    st.dataframe(
        lb_df.style
        .background_gradient(subset=["1m %", "3m %"], cmap="RdYlGn")
        .format({"Price": "{:.2f}", "Today %": "{:+.2f}%", "1w %": "{:.2f}", "1m %": "{:.2f}",
                 "3m %": "{:.2f}", "12m %": "{:.2f}"}),
        use_container_width=True, hide_index=True,
    )

    strong, weak = ms.summarize_sector_strength(sector_leaderboard)
    strong_etfs = ms.strong_sector_etfs(sector_leaderboard)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="card"><b>🟢 Sectors showing strength</b><br>' +
            (", ".join(f"{s} ({e})" for s, e in strong) or "n/a") + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="card"><b>🔴 Sectors showing weakness</b><br>' +
            (", ".join(f"{s} ({e})" for s, e in weak) or "n/a") + "</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("Sector leaderboard unavailable right now (data fetch issue). Try refreshing.")


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Scan settings")

    UNIVERSE_LABELS = {
        "S&P 500 (large-cap)": "sp500",
        "S&P 400 (mid-cap)": "sp400",
        "S&P 600 (small-cap)": "sp600",
        "All combined (500+400+600)": "all",
    }

    mode = st.radio("Ticker universe", ["Manual list", "Index universe"], index=0)

    if mode == "Manual list":
        default_list = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, JPM, XOM, SPY, XLK"
        tickers_input = st.text_area("Tickers (comma-separated) — stocks and ETFs both OK",
                                      value=default_list, height=100)
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    else:
        universe_label = st.selectbox("Which index?", list(UNIVERSE_LABELS.keys()))
        universe_key = UNIVERSE_LABELS[universe_label]
        universe_total = len(ms.get_universe_tickers(universe_key))
        n = st.slider(f"How many tickers to scan (1–{universe_total})", 1, universe_total,
                      min(50, universe_total))
        st.caption(f"Scans the first {n} of {universe_total} tickers in {universe_label}.")
        if n > 150:
            st.info("Scanning more than ~150 tickers can take several minutes due to Yahoo Finance rate limits.")
        tickers = ms.get_universe_tickers(universe_key, n)

    only_strong = st.checkbox(
        "Only show stocks from currently-strong sectors", value=True,
        help="Per Murphy's sector-rotation approach: focus only on stocks whose sector is in the "
             "top third of the relative-strength leaderboard above. ETFs are never filtered by this.",
    )

    top_n = st.slider("Number of results to show (per list)", 5, 50, 20)
    run_button = st.button("🔍 Run scan", type="primary", use_container_width=True)

    st.markdown("---")
    st.caption("Scoring weights: Trend 25 · MA50 setup 10 · Bollinger 10 · Candlestick 10 · "
               "Volume 10 · RSI 10 · MACD 10 · Sector strength 10 · Macro regime 5")


# ---------------------------------------------------------------------------
# Relative-strength chart helper (stock vs SPY, normalized to 100)
# ---------------------------------------------------------------------------
def render_relative_strength_chart(ticker, stock_df):
    spy_df = cached_history("SPY")
    rel = ms.get_relative_strength_series(stock_df, spy_df, lookback=126)
    if rel is None:
        st.caption("Not enough data to draw a relative-strength chart.")
        return
    st.caption(f"{ticker} vs. SPY — rebased to 100, last {len(rel)} trading days. "
               "If the stock's line is above SPY's, it's outperforming the market.")
    st.line_chart(rel, use_container_width=True, height=220)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------
if run_button:
    if not tickers:
        st.warning("No tickers entered.")
        st.stop()

    regime = cached_regime()
    sector_leaderboard_scan = cached_sector_leaderboard()
    strong_etfs_scan = ms.strong_sector_etfs(sector_leaderboard_scan) if sector_leaderboard_scan else set()

    st.markdown(f'<div class="section-title">📋 Scan Results ({len(tickers)} tickers)</div>', unsafe_allow_html=True)
    progress = st.progress(0.0, text="Starting scan...")
    stock_results, etf_results, skipped_weak = [], [], 0
    for i, ticker in enumerate(tickers, start=1):
        progress.progress(i / len(tickers), text=f"Scanning {ticker} ({i}/{len(tickers)})")
        try:
            df = cached_history(ticker)
            if df is None:
                continue
            etf_flag = cached_is_etf(ticker)
            sector = "ETF" if etf_flag else cached_sector(ticker)
            if not etf_flag and only_strong and strong_etfs_scan:
                if not ms.stock_is_in_strong_sector(sector, sector_leaderboard_scan, strong_etfs_scan):
                    skipped_weak += 1
                    continue
            res = ms.score_stock(ticker, df, sector, sector_leaderboard_scan, regime, is_etf=etf_flag)
            (etf_results if etf_flag else stock_results).append(res)
        except Exception as e:
            st.warning(f"Skipped {ticker}: {e}")
    progress.empty()

    if only_strong and skipped_weak:
        st.caption(f"ℹ️ Skipped {skipped_weak} stocks outside the currently-strong sectors "
                   "(uncheck the sidebar option to include them).")

    if not stock_results and not etf_results:
        st.error("No results returned. Check your tickers/filters and try again.")
        st.stop()

    display_cols = ["Ticker", "Score", "Sector", "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]
    money_cols = ["Price", "StopLoss", "Target", "R:R"]

    def render_results(results, title, icon, csv_name, show_rs_chart=False):
        if not results:
            return
        df_out = pd.DataFrame(results).sort_values("Score", ascending=False).head(top_n)

        st.markdown(f'<div class="section-title">{icon} {title} ({len(results)} found)</div>', unsafe_allow_html=True)
        st.dataframe(
            df_out[display_cols]
            .style.background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100)
            .format({c: "{:.2f}" for c in money_cols}),
            use_container_width=True, hide_index=True,
        )

        st.markdown(f'<div class="section-title">🔎 {title} — Per-Ticker Breakdown</div>', unsafe_allow_html=True)
        for _, row in df_out.iterrows():
            header = f"{row['Ticker']} — {row['Sector']}"
            with st.expander(header):
                st.markdown(
                    f'{score_badge(row["Score"])} &nbsp; <span class="sector-chip">{row["Sector"]}</span>',
                    unsafe_allow_html=True,
                )
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Price", f"{row['Price']:.2f}")
                c2.metric("Stop-loss", f"{row['StopLoss']:.2f}")
                c3.metric("Target", f"{row['Target']:.2f}")
                c4.metric("R:R", f"{row['R:R']:.2f}" if row["R:R"] is not None else "n/a")
                st.markdown("**Why it scored this way:**")
                for r in row["Reasons"]:
                    st.markdown(f'<div class="reason-item">• {r}</div>', unsafe_allow_html=True)
                if show_rs_chart:
                    st.markdown("**Relative strength vs. SPY:**")
                    stock_df = cached_history(row["Ticker"])
                    render_relative_strength_chart(row["Ticker"], stock_df)

        csv = df_out.assign(Reasons=df_out["Reasons"].apply(lambda r: " | ".join(r))).to_csv(index=False).encode("utf-8-sig")
        st.download_button(f"⬇️ Download {title} CSV", csv, csv_name, "text/csv",
                            use_container_width=True, key=csv_name)

    render_results(stock_results, "Stocks", "📈", "screener_results_stocks.csv", show_rs_chart=True)
    render_results(etf_results, "ETFs", "🧺", "screener_results_etfs.csv", show_rs_chart=False)

else:
    st.info("Set your tickers in the sidebar and click **Run scan**.")
