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


@st.cache_data(ttl=300, show_spinner=False)
def cached_market_snapshot():
    return ms.get_market_snapshot()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_normalized_comparison(tickers_tuple, lookback=252):
    return ms.get_normalized_comparison(dict(tickers_tuple), lookback=lookback)


# ---------------------------------------------------------------------------
# TABS: Home (live snapshot + regime + leaderboard + scan) / Charts
# ---------------------------------------------------------------------------
tab_home, tab_charts = st.tabs(["🏠 Home", "📊 Charts"])

with tab_home:
    st.markdown('<div class="section-title">💱 Live Market Snapshot</div>', unsafe_allow_html=True)
    with st.spinner("Fetching FX / commodities / bond prices..."):
        snapshot = cached_market_snapshot()
    snap_cols = st.columns(len(snapshot))
    for col, (label, info) in zip(snap_cols, snapshot.items()):
        if info["price"] is None:
            col.metric(label, "n/a")
        else:
            col.metric(label, f"{info['price']:.2f}",
                       delta=f"{info['day_change_pct']:+.2f}%" if info["day_change_pct"] is not None else None)

    st.markdown('<div class="section-title">🌍 Current Intermarket Regime</div>', unsafe_allow_html=True)
    with st.spinner("Reading the intermarket regime (SPY / TLT / DBC / UUP)..."):
        regime = cached_regime()
    st.markdown(f'<div class="card">{regime["description"]}</div>', unsafe_allow_html=True)
    trend_cols = st.columns(4)
    arrow_map = {"up": "🟢 Rising", "down": "🔴 Falling", "flat": "⚪ Flat", "unknown": "❓ Unknown"}
    trends_pct = regime.get("trends_pct", {})
    for col, (name, trend) in zip(trend_cols, regime["trends"].items()):
        pct = trends_pct.get(name)
        delta = f"{pct:+.2f}% (20d)" if pct is not None else None
        col.metric(name, arrow_map.get(trend, trend), delta=delta)
    st.caption("Direction compares each proxy's 60-day moving average to itself 20 trading days ago. "
               "'Flat' means that move was smaller than ±0.5% — a genuinely quiet trend, not missing data.")

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

with tab_charts:
    st.markdown('<div class="section-title">📊 SPY vs. Commodities / Bonds / Dollar</div>', unsafe_allow_html=True)
    st.caption("All series rebased to 100 at the start of the window, last ~1 year of trading days.")
    macro_tickers = (("SPY", "SPY"), ("Commodities (DBC)", "DBC"), ("Bonds (TLT)", "TLT"), ("Dollar (UUP)", "UUP"))
    macro_chart = cached_normalized_comparison(macro_tickers, 252)
    if macro_chart is not None:
        st.line_chart(macro_chart, use_container_width=True, height=320)
    else:
        st.info("Not enough data to build this chart right now.")

    st.markdown('<div class="section-title">🏭 SPY vs. Each Sector</div>', unsafe_allow_html=True)
    st.caption("Every sector SPDR ETF alongside SPY, all rebased to 100. Lines above SPY are outperforming.")
    sector_tickers = [("SPY", "SPY")] + sorted(
        {(f"{sector} ({etf})", etf) for sector, etf in
         [("Information Technology", "XLK"), ("Financials", "XLF"), ("Energy", "XLE"),
          ("Health Care", "XLV"), ("Consumer Discretionary", "XLY"), ("Consumer Staples", "XLP"),
          ("Industrials", "XLI"), ("Materials", "XLB"), ("Utilities", "XLU"),
          ("Real Estate", "XLRE"), ("Communication Services", "XLC")]}
    )
    sector_chart = cached_normalized_comparison(tuple(sector_tickers), 252)
    if sector_chart is not None:
        st.line_chart(sector_chart, use_container_width=True, height=420)
    else:
        st.info("Not enough data to build this chart right now.")

    st.markdown('<div class="section-title">🔍 Individual Sector vs. SPY</div>', unsafe_allow_html=True)
    pick_sector = st.selectbox(
        "Pick one sector to compare closely against SPY",
        ["Information Technology", "Financials", "Energy", "Health Care", "Consumer Discretionary",
         "Consumer Staples", "Industrials", "Materials", "Utilities", "Real Estate",
         "Communication Services"],
    )
    pick_etf = dict([("Information Technology", "XLK"), ("Financials", "XLF"), ("Energy", "XLE"),
                      ("Health Care", "XLV"), ("Consumer Discretionary", "XLY"), ("Consumer Staples", "XLP"),
                      ("Industrials", "XLI"), ("Materials", "XLB"), ("Utilities", "XLU"),
                      ("Real Estate", "XLRE"), ("Communication Services", "XLC")])[pick_sector]
    single_chart = cached_normalized_comparison((("SPY", "SPY"), (f"{pick_sector} ({pick_etf})", pick_etf)), 252)
    if single_chart is not None:
        st.line_chart(single_chart, use_container_width=True, height=280)
    else:
        st.info("Not enough data to build this chart right now.")


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
        "My Watchlist (global ADRs)": "watchlist",
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

    use_beta_filter = st.checkbox("Filter by minimum beta", value=True)
    min_beta = st.slider("Minimum beta (vs. SPY)", 0.0, 3.0, 1.0, 0.1, disabled=not use_beta_filter,
                         help="Beta is computed directly from each stock's own price history vs. SPY "
                              "(1-year daily returns), not pulled from an external data field.")

    only_actionable = st.checkbox(
        "Only show actionable setups (Buy Zone / Watchlist)", value=True,
        help="'Buy Zone' = a concrete trigger is present right now (support test, bullish candle, or "
             "unusual volume). 'Watchlist' = strong trend/squeeze forming, worth monitoring for a trigger "
             "in the next few days. Unchecking this also shows generic trending stocks with no trigger at all.",
    )

    require_volume_spike = st.checkbox(
        "Only show stocks with a volume spike (≥1.5x avg, today or yesterday)", value=False,
        help="A strong potential-move indicator: today's OR yesterday's volume was at least 1.5x the "
             "20-day average. Off by default — turn on to focus specifically on volume-confirmed names.",
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


with tab_home:
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
        spy_df_scan = cached_history("SPY")
        spy_close_scan = spy_df_scan["Close"] if spy_df_scan is not None else None
        effective_min_beta = min_beta if use_beta_filter else None

        st.markdown(f'<div class="section-title">📋 Scan Results ({len(tickers)} tickers)</div>', unsafe_allow_html=True)
        progress = st.progress(0.0, text="Starting scan...")
        stock_results, etf_results = [], []
        skipped_weak = skipped_beta = skipped_no_signal = skipped_no_vol_spike = 0
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
                res = ms.score_stock(ticker, df, sector, sector_leaderboard_scan, regime,
                                      is_etf=etf_flag, spy_close=spy_close_scan)
                if not etf_flag:
                    if effective_min_beta is not None and res["Beta"] is not None and res["Beta"] < effective_min_beta:
                        skipped_beta += 1
                        continue
                    if only_actionable and res["Setup"] == "No Signal":
                        skipped_no_signal += 1
                        continue
                    if require_volume_spike and not res["VolumeSpike"]:
                        skipped_no_vol_spike += 1
                        continue
                (etf_results if etf_flag else stock_results).append(res)
            except Exception as e:
                st.warning(f"Skipped {ticker}: {e}")
        progress.empty()

        filter_notes = []
        if only_strong and skipped_weak:
            filter_notes.append(f"{skipped_weak} outside the currently-strong sectors")
        if effective_min_beta is not None and skipped_beta:
            filter_notes.append(f"{skipped_beta} with beta below {effective_min_beta}")
        if only_actionable and skipped_no_signal:
            filter_notes.append(f"{skipped_no_signal} with no actionable setup")
        if require_volume_spike and skipped_no_vol_spike:
            filter_notes.append(f"{skipped_no_vol_spike} without a {ms.RECENT_VOLUME_SPIKE_MULT}x+ volume spike")
        if filter_notes:
            st.caption("ℹ️ Skipped " + "; ".join(filter_notes) + " (adjust the sidebar filters to include them).")

        if not stock_results and not etf_results:
            st.error("No results returned. Check your tickers/filters and try again.")
            st.stop()

        display_cols = ["Ticker", "Score", "Setup", "Sector", "Beta", "VolumeSpikeRatio", "VolumeSpikeDay",
                         "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]
        money_cols = ["Price", "StopLoss", "Target", "R:R"]
        SETUP_SORT_ORDER = {"Buy Zone": 0, "Watchlist": 1, "No Signal": 2}

        def setup_badge(setup):
            colors = {"Buy Zone": "badge-high", "Watchlist": "badge-mid", "No Signal": "badge-low"}
            return f'<span class="badge {colors.get(setup, "badge-low")}">{setup}</span>'

        def render_results(results, title, icon, csv_name, show_rs_chart=False, sort_by_setup=False):
            if not results:
                return
            df_out = pd.DataFrame(results)
            if sort_by_setup:
                df_out = df_out.assign(_s=df_out["Setup"].map(SETUP_SORT_ORDER).fillna(9)).sort_values(
                    ["_s", "Score"], ascending=[True, False]).drop(columns="_s")
            else:
                df_out = df_out.sort_values("Score", ascending=False)
            df_out = df_out.head(top_n)

            st.markdown(f'<div class="section-title">{icon} {title} ({len(results)} found)</div>', unsafe_allow_html=True)
            format_map = {c: "{:.2f}" for c in money_cols}
            format_map["Beta"] = "{:.2f}"
            format_map["VolumeSpikeRatio"] = "{:.2f}"
            st.dataframe(
                df_out[display_cols]
                .style.background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100)
                .format(format_map, na_rep="n/a"),
                use_container_width=True, hide_index=True,
            )

            st.markdown(f'<div class="section-title">🔎 {title} — Per-Ticker Breakdown</div>', unsafe_allow_html=True)
            for _, row in df_out.iterrows():
                header = f"{row['Ticker']} — {row['Sector']}"
                with st.expander(header):
                    beta_txt = f"Beta {row['Beta']:.2f}" if row["Beta"] is not None else "Beta n/a"
                    badges = (f'{score_badge(row["Score"])} &nbsp; {setup_badge(row["Setup"])} &nbsp; '
                              f'<span class="sector-chip">{row["Sector"]}</span> &nbsp; '
                              f'<span class="sector-chip">{beta_txt}</span>')
                    if row.get("VolumeSpike"):
                        badges += (f' &nbsp; <span class="sector-chip">🔊 {row["VolumeSpikeRatio"]:.1f}x '
                                   f'volume ({row["VolumeSpikeDay"]})</span>')
                    st.markdown(badges, unsafe_allow_html=True)
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

        render_results(stock_results, "Stocks", "📈", "screener_results_stocks.csv", show_rs_chart=True, sort_by_setup=True)
        render_results(etf_results, "ETFs", "🧺", "screener_results_etfs.csv", show_rs_chart=False)

    else:
        st.info("Set your tickers in the sidebar and click **Run scan**.")
