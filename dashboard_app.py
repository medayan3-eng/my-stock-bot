"""
dashboard_app.py
Streamlit UI for the Murphy Screener.

Deploy this as your Streamlit Cloud main module. It needs
murphy_screener.py and sp500_tickers.csv in the SAME folder/repo.
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


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Scan settings")

    mode = st.radio("Ticker universe", ["Manual list", "Full S&P 500 (slow)"], index=0)

    if mode == "Manual list":
        default_list = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, JPM, XOM"
        tickers_input = st.text_area("Tickers (comma-separated)", value=default_list, height=100)
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    else:
        st.info("Scanning the full S&P 500 can take several minutes due to Yahoo Finance rate limits.")
        tickers = ms.get_sp500_tickers()

    top_n = st.slider("Number of results to show", 5, 50, 20)
    run_button = st.button("🔍 Run scan", type="primary", use_container_width=True)

    st.markdown("---")
    st.caption("Scoring weights: Trend 25 · MA50 setup 10 · Bollinger 10 · Candlestick 10 · "
               "Volume 10 · RSI 10 · MACD 10 · Sector strength 10 · Macro regime 5")


# ---------------------------------------------------------------------------
# Cached data fetchers (avoid re-hitting Yahoo Finance on every rerun)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def cached_regime():
    return ms.get_intermarket_regime()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_sector_leaderboard():
    return ms.get_sector_leaderboard()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_history(ticker):
    return ms.fetch_history(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_sector(ticker):
    return ms.get_sector(ticker)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------
if run_button:
    if not tickers:
        st.warning("No tickers entered.")
        st.stop()

    with st.spinner("Reading the intermarket regime (SPY / TLT / DBC / UUP)..."):
        regime = cached_regime()

    st.markdown('<div class="section-title">🌍 Current Intermarket Regime</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="card">{regime["description"]}</div>', unsafe_allow_html=True)
    trend_cols = st.columns(4)
    arrow_map = {"up": "🟢 Rising", "down": "🔴 Falling", "flat": "⚪ Flat", "unknown": "❓ Unknown"}
    for col, (name, trend) in zip(trend_cols, regime["trends"].items()):
        col.metric(name, arrow_map.get(trend, trend))

    with st.spinner("Building sector relative-strength leaderboard..."):
        sector_leaderboard = cached_sector_leaderboard()

    if sector_leaderboard:
        st.markdown('<div class="section-title">🏭 Sector Leaderboard (vs. SPY)</div>', unsafe_allow_html=True)
        lb_rows = []
        for etf, info in sorted(sector_leaderboard.items(), key=lambda kv: kv[1]["rank"]):
            lb_rows.append({
                "Rank": info["rank"], "Sector": info["sector"], "ETF": etf,
                "1w %": round(info["1w"], 2) if info["1w"] == info["1w"] else None,
                "1m %": round(info["1m"], 2) if info["1m"] == info["1m"] else None,
                "3m %": round(info["3m"], 2) if info["3m"] == info["3m"] else None,
                "12m %": round(info["12m"], 2) if info["12m"] == info["12m"] else None,
            })
        lb_df = pd.DataFrame(lb_rows)
        st.dataframe(
            lb_df.style.background_gradient(subset=["1m %", "3m %"], cmap="RdYlGn"),
            use_container_width=True, hide_index=True,
        )

    st.markdown(f'<div class="section-title">📋 Scan Results ({len(tickers)} tickers)</div>', unsafe_allow_html=True)
    progress = st.progress(0.0, text="Starting scan...")
    results = []
    for i, ticker in enumerate(tickers, start=1):
        progress.progress(i / len(tickers), text=f"Scanning {ticker} ({i}/{len(tickers)})")
        try:
            df = cached_history(ticker)
            if df is None:
                continue
            sector = cached_sector(ticker)
            res = ms.score_stock(ticker, df, sector, sector_leaderboard, regime)
            results.append(res)
        except Exception as e:
            st.warning(f"Skipped {ticker}: {e}")
    progress.empty()

    if not results:
        st.error("No results returned. Check your tickers and try again.")
        st.stop()

    df_out = pd.DataFrame(results).sort_values("Score", ascending=False).head(top_n)

    st.dataframe(
        df_out[["Ticker", "Score", "Sector", "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]]
        .style.background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100),
        use_container_width=True, hide_index=True,
    )

    st.markdown('<div class="section-title">🔎 Per-Stock Breakdown</div>', unsafe_allow_html=True)
    for _, row in df_out.iterrows():
        header = f"{row['Ticker']} — {row['Sector']}"
        with st.expander(header):
            st.markdown(
                f'{score_badge(row["Score"])} &nbsp; <span class="sector-chip">{row["Sector"]}</span>',
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Price", row["Price"])
            c2.metric("Stop-loss", row["StopLoss"])
            c3.metric("Target", row["Target"])
            c4.metric("R:R", row["R:R"])
            st.markdown("**Why it scored this way:**")
            for r in row["Reasons"]:
                st.markdown(f'<div class="reason-item">• {r}</div>', unsafe_allow_html=True)

    csv = df_out.assign(Reasons=df_out["Reasons"].apply(lambda r: " | ".join(r))).to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Download full CSV", csv, "screener_results.csv", "text/csv", use_container_width=True)

else:
    st.info("Set your tickers in the sidebar and click **Run scan**.")
