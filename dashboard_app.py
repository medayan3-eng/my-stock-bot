"""
dashboard_app.py
Streamlit UI for the Murphy Screener. Deploy this as your Streamlit Cloud
main module (filename must match what you set in the app settings — this
file is named dashboard_app.py to match the error you saw).

Needs murphy_screener.py in the SAME folder/repo — it reuses all the
indicator/scoring logic from there instead of duplicating it.
"""

import streamlit as st
import pandas as pd

import murphy_screener as ms

st.set_page_config(page_title="Murphy Screener", layout="wide")

st.title("📊 Murphy Screener")
st.caption("סורק מניות (לא בוט מסחר) לפי עקרונות מרפי — מגמה, בולינגר, נרות, נפח, RSI/MACD, סקטורים ואינטרמרקט.")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("הגדרות סריקה")

    mode = st.radio("רשימת מניות", ["רשימה ידנית", "S&P 500 (איטי!)"], index=0)

    if mode == "רשימה ידנית":
        default_list = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, JPM, XOM"
        tickers_input = st.text_area("טיקרים (מופרדים בפסיק)", value=default_list, height=100)
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    else:
        st.info("סריקת כל ה-S&P 500 יכולה לקחת כמה דקות בגלל מגבלות קצב של Yahoo Finance.")
        tickers = ms.get_sp500_tickers()

    top_n = st.slider("כמה תוצאות להציג", 5, 50, 20)
    run_button = st.button("🔍 הרץ סריקה", type="primary")


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
    try:
        t = ms.yf.Ticker(ticker)
        return ms.get_sector(t)
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------
if run_button:
    if not tickers:
        st.warning("לא הוזנו טיקרים.")
        st.stop()

    with st.spinner("בודק את משטר האינטרמרקט (SPY/TLT/DBC/UUP)..."):
        regime = cached_regime()

    st.subheader("🌍 משטר אינטרמרקט נוכחי")
    st.write(regime["description"])
    trend_cols = st.columns(4)
    for col, (name, trend) in zip(trend_cols, regime["trends"].items()):
        arrow = {"up": "🟢 עולה", "down": "🔴 יורד", "flat": "⚪ שטוח", "unknown": "❓"}[trend]
        col.metric(name, arrow)

    with st.spinner("בונה טבלת חוזק סקטוריאלי..."):
        sector_leaderboard = cached_sector_leaderboard()

    if sector_leaderboard:
        st.subheader("🏭 דירוג סקטורים (מול SPY)")
        lb_rows = []
        for etf, info in sorted(sector_leaderboard.items(), key=lambda kv: kv[1]["rank"]):
            lb_rows.append({
                "דירוג": info["rank"], "סקטור": info["sector"], "ETF": etf,
                "1 שבוע %": round(info["1w"], 2) if info["1w"] == info["1w"] else None,
                "1 חודש %": round(info["1m"], 2) if info["1m"] == info["1m"] else None,
                "3 חודשים %": round(info["3m"], 2) if info["3m"] == info["3m"] else None,
                "12 חודשים %": round(info["12m"], 2) if info["12m"] == info["12m"] else None,
            })
        st.dataframe(pd.DataFrame(lb_rows), use_container_width=True, hide_index=True)

    st.subheader(f"📋 תוצאות סריקה ({len(tickers)} טיקרים)")
    progress = st.progress(0.0, text="מתחיל סריקה...")
    results = []
    for i, ticker in enumerate(tickers, start=1):
        progress.progress(i / len(tickers), text=f"סורק {ticker} ({i}/{len(tickers)})")
        try:
            df = cached_history(ticker)
            if df is None:
                continue
            sector = cached_sector(ticker)
            res = ms.score_stock(ticker, df, sector, sector_leaderboard, regime)
            results.append(res)
        except Exception as e:
            st.warning(f"דילגתי על {ticker}: {e}")
    progress.empty()

    if not results:
        st.error("לא התקבלו תוצאות. בדוק את הטיקרים ונסה שוב.")
        st.stop()

    df_out = pd.DataFrame(results).sort_values("Score", ascending=False).head(top_n)

    display_cols = ["Ticker", "Score", "Sector", "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]
    st.dataframe(
        df_out[display_cols].rename(columns={
            "Ticker": "טיקר", "Score": "ציון", "Sector": "סקטור", "Price": "מחיר",
            "StopLoss": "סטופ לוס", "Target": "יעד", "RSI": "RSI", "SectorRank": "דירוג סקטור",
        }),
        use_container_width=True, hide_index=True,
    )

    st.subheader("🔎 פירוט מלא לפי מניה")
    for _, row in df_out.iterrows():
        with st.expander(f"{row['Ticker']} — ציון {row['Score']} — {row['Sector']}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("מחיר", row["Price"])
            c2.metric("סטופ לוס", row["StopLoss"])
            c3.metric("יעד", row["Target"])
            c4.metric("R:R", row["R:R"])
            st.markdown("**למה קיבלה את הציון:**")
            for r in row["Reasons"]:
                st.markdown(f"- {r}")

    csv = df_out.assign(Reasons=df_out["Reasons"].apply(lambda r: " | ".join(r))).to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ הורד CSV מלא", csv, "screener_results.csv", "text/csv")

else:
    st.info("הגדר טיקרים בסרגל הצד ולחץ 'הרץ סריקה'.")
