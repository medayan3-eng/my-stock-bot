"""
Murphy Stock Screener
======================
Screener/indicator tool (NOT an auto-trader) built on the principles from
John Murphy's "Technical Analysis of the Financial Markets" and
"Intermarket Analysis", used together with sector-relative-strength and
candlestick confirmation.

The bot does NOT place trades. It scans a universe of stocks, scores each
one 0-100, and prints/exports a ranked table with a plain-language
explanation of WHY each stock scored the way it did, plus a suggested
stop-loss and price target. You take it from there.

REQUIREMENTS (run this locally, not in a sandboxed/offline environment):
    pip install yfinance pandas numpy

USAGE:
    python murphy_screener.py                     # scans default S&P 500 list
    python murphy_screener.py AAPL MSFT NVDA       # scans just these tickers
    python murphy_screener.py --file mylist.txt    # one ticker per line
    python murphy_screener.py --top 30             # show only top 30 by score

Output: prints a ranked table to the console AND writes
        screener_results.csv in the same folder.
"""

import sys
import argparse
import datetime as dt
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Missing dependency. Run:  pip install yfinance pandas numpy")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

LOOKBACK_DAYS = 400          # trading days of history to pull (~ covers 52w + 200MA warmup)
VOLUME_SPIKE_MULT = 2.0      # today's volume vs 20d avg volume to count as "unusual"
NEAR_MA50_PCT = 0.03         # "hugging the 50MA" = within 3%
BREAKOUT_LOOKBACK = 20       # bars used to define "recent swing low" for stop-loss

# GICS sector -> representative SPDR sector ETF, used for relative-strength ranking
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# Intermarket regime proxies (Murphy's four-market model)
INTERMARKET_TICKERS = {
    "stocks": "SPY",
    "bonds": "TLT",     # long-term treasuries -> proxy for interest-rate direction (inverse of yields)
    "commodities": "DBC",
    "dollar": "UUP",
}

BENCHMARK = "SPY"


# ---------------------------------------------------------------------------
# DATA FETCH
# ---------------------------------------------------------------------------

def fetch_history(ticker, period_days=LOOKBACK_DAYS):
    end = dt.date.today()
    start = end - dt.timedelta(days=int(period_days * 1.6))  # buffer for weekends/holidays
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 210:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    return df


def get_sp500_tickers():
    """Best-effort fetch of the S&P 500 list from Wikipedia. Falls back to a
    small hardcoded sample if that fails (e.g., no internet / blocked)."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = tables[0]["Symbol"].tolist()
        return [t.replace(".", "-") for t in tickers]
    except Exception:
        print("Could not fetch S&P 500 list from Wikipedia, using a small fallback list.")
        return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA",
                "JPM", "XOM", "UNH", "V", "PG", "HD", "COST", "LLY"]


def get_sector(ticker_obj):
    try:
        info = ticker_obj.info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------

def sma(series, window):
    return series.rolling(window).mean()


def bollinger_bands(close, window=20, num_std=2):
    mid = sma(close, window)
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid
    return upper, mid, lower, width


def rsi(close, window=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def is_bullish_engulfing(o, h, l, c):
    # last two candles: prior red, current green, current body engulfs prior body
    prev_o, prev_c = o.iloc[-2], c.iloc[-2]
    cur_o, cur_c = o.iloc[-1], c.iloc[-1]
    return (prev_c < prev_o) and (cur_c > cur_o) and (cur_c >= prev_o) and (cur_o <= prev_c)


def is_hammer(o, h, l, c):
    cur_o, cur_c, cur_h, cur_l = o.iloc[-1], c.iloc[-1], h.iloc[-1], l.iloc[-1]
    body = abs(cur_c - cur_o)
    full_range = cur_h - cur_l
    if full_range <= 0:
        return False
    lower_shadow = min(cur_o, cur_c) - cur_l
    upper_shadow = cur_h - max(cur_o, cur_c)
    # small body near top of range, long lower shadow, little/no upper shadow
    return (lower_shadow >= 2 * body) and (upper_shadow <= 0.3 * body + 0.02 * full_range) and (body <= 0.35 * full_range)


def is_piercing_line(o, h, l, c):
    prev_o, prev_c = o.iloc[-2], c.iloc[-2]
    cur_o, cur_c = o.iloc[-1], c.iloc[-1]
    prev_mid = (prev_o + prev_c) / 2
    return (prev_c < prev_o) and (cur_c > cur_o) and (cur_o < prev_c) and (cur_c > prev_mid) and (cur_c < prev_o)


def is_morning_star(o, h, l, c):
    if len(c) < 3:
        return False
    o1, c1 = o.iloc[-3], c.iloc[-3]
    o2, c2 = o.iloc[-2], c.iloc[-2]
    o3, c3 = o.iloc[-1], c.iloc[-1]
    day1_bearish = c1 < o1
    day2_small = abs(c2 - o2) < abs(c1 - o1) * 0.5
    day3_bullish_recovery = (c3 > o3) and (c3 > (o1 + c1) / 2)
    return day1_bearish and day2_small and day3_bullish_recovery


def detect_bullish_candle(df):
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    hits = []
    try:
        if is_hammer(o, h, l, c):
            hits.append("פטיש (Hammer) בסוף ירידה")
        if is_bullish_engulfing(o, h, l, c):
            hits.append("נר בליעה חיובי (Bullish Engulfing)")
        if is_piercing_line(o, h, l, c):
            hits.append("תבנית חדירה (Piercing Line)")
        if is_morning_star(o, h, l, c):
            hits.append("כוכב בוקר (Morning Star)")
    except Exception:
        pass
    return hits


# ---------------------------------------------------------------------------
# INTERMARKET REGIME (Murphy's Intermarket Analysis)
# ---------------------------------------------------------------------------

def trend_direction(close, window=60):
    """Simple slope-based trend: is the N-day SMA rising or falling?"""
    ma = sma(close, window)
    if len(ma.dropna()) < 10:
        return "flat"
    recent = ma.dropna().iloc[-1]
    prior = ma.dropna().iloc[-10]
    if recent > prior * 1.01:
        return "up"
    elif recent < prior * 0.99:
        return "down"
    return "flat"


def get_intermarket_regime():
    """Classify the macro regime using bonds/stocks/commodities/dollar trends,
    per Murphy's four-market model + Pring's six-stage business cycle map."""
    trends = {}
    for name, ticker in INTERMARKET_TICKERS.items():
        df = fetch_history(ticker, period_days=250)
        if df is None:
            trends[name] = "unknown"
        else:
            trends[name] = trend_direction(df["Close"])

    bonds, stocks, commodities, dollar = (trends.get(k, "unknown") for k in
                                           ["bonds", "stocks", "commodities", "dollar"])

    # Bonds (TLT) rising == interest rates falling; bonds falling == rates rising
    if commodities == "up" and bonds == "down":
        regime = "אינפלציוני מוקדם/אמצעי: סחורות עולות, אג\"ח יורדות (ריבית עולה) — עדיפות לסחורות/אנרגיה, זהירות במניות ריבית-רגישות"
        favored = ["Energy", "Basic Materials"]
    elif commodities == "down" and bonds == "up":
        regime = "דיפלציוני/האטה: סחורות יורדות, אג\"ח עולות (ריבית יורדת) — עדיפות לאג\"ח ומניות דפנסיביות"
        favored = ["Utilities", "Consumer Defensive", "Healthcare"]
    elif stocks == "up" and bonds == "up":
        regime = "התרחבות בריאה מוקדמת: גם מניות וגם אג\"ח עולות — סביבה חיובית למניות צמיחה"
        favored = ["Technology", "Financial Services", "Consumer Cyclical"]
    elif stocks == "down" and commodities == "down" and bonds == "down":
        regime = "שלב 6 (הכל יורד) — Cash is King, זהירות מוגברת בכל הפוזיציות"
        favored = []
    else:
        regime = f"מעורב/לא חד-משמעי (מניות={stocks}, אג\"ח={bonds}, סחורות={commodities}, דולר={dollar})"
        favored = []

    return {"trends": trends, "description": regime, "favored_sectors": favored}


# ---------------------------------------------------------------------------
# SECTOR RELATIVE STRENGTH
# ---------------------------------------------------------------------------

def get_sector_leaderboard():
    """Rank each sector ETF's relative performance vs SPY over 1w/1m/3m/12m."""
    spy = fetch_history(BENCHMARK, period_days=280)
    if spy is None:
        return {}
    spy_close = spy["Close"]

    results = {}
    seen_etfs = set()
    for sector, etf in SECTOR_ETFS.items():
        if etf in seen_etfs:
            continue
        seen_etfs.add(etf)
        df = fetch_history(etf, period_days=280)
        if df is None:
            continue
        close = df["Close"]

        def rel_perf(n):
            if len(close) <= n or len(spy_close) <= n:
                return np.nan
            stock_ret = close.iloc[-1] / close.iloc[-n] - 1
            spy_ret = spy_close.iloc[-1] / spy_close.iloc[-n] - 1
            return (stock_ret - spy_ret) * 100  # percentage points vs SPY

        results[etf] = {
            "1w": rel_perf(5),
            "1m": rel_perf(21),
            "3m": rel_perf(63),
            "12m": rel_perf(252),
        }

    # rank sectors by average of 1m + 3m relative strength (medium-term leadership)
    ranked = sorted(results.items(), key=lambda kv: np.nanmean([kv[1]["1m"], kv[1]["3m"]]), reverse=True)
    etf_to_sector = {}
    for sector, etf in SECTOR_ETFS.items():
        etf_to_sector.setdefault(etf, sector)

    leaderboard = {}
    for rank, (etf, perf) in enumerate(ranked, start=1):
        leaderboard[etf] = {"rank": rank, "sector": etf_to_sector[etf], **perf}
    return leaderboard


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def score_stock(ticker, df, sector, sector_leaderboard, regime):
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]
    open_ = df["Open"]

    last_close = close.iloc[-1]
    reasons = []
    score = 0

    # --- 1. 52-week trend template (25 pts) ---------------------------------
    ma50 = sma(close, 50)
    ma200 = sma(close, 200)
    week52_high = close.rolling(252).max().iloc[-1]
    week52_low = close.rolling(252).min().iloc[-1]
    price_52w_ago = close.iloc[-252] if len(close) >= 252 else close.iloc[0]

    trend_pts = 0
    if last_close > price_52w_ago:
        trend_pts += 8
        reasons.append("המניה גבוהה מהמחיר לפני 52 שבועות (מגמת עלייה שנתית)")
    if last_close > ma50.iloc[-1] and last_close > ma200.iloc[-1]:
        trend_pts += 10
        reasons.append("המחיר מעל הממוצע הנע 50 ומעל 200 (מגמת עלייה מאושרת)")
    if ma50.iloc[-1] > ma200.iloc[-1]:
        trend_pts += 4
        reasons.append("ממוצע 50 מעל ממוצע 200 (Golden Cross structure)")
    if last_close >= week52_high * 0.75:
        trend_pts += 3
        reasons.append("המניה בטווח של עד 25% מהשיא ב-52 שבועות")
    score += min(trend_pts, 25)

    # --- 2. Near-MA50 pullback opportunity on volume (10 pts) ---------------
    near_ma50_pts = 0
    dist_from_ma50 = abs(last_close - ma50.iloc[-1]) / ma50.iloc[-1]
    avg_vol20 = vol.rolling(20).mean().iloc[-1]
    vol_today = vol.iloc[-1]
    if dist_from_ma50 <= NEAR_MA50_PCT and last_close >= ma50.iloc[-1] * 0.98:
        near_ma50_pts += 5
        reasons.append("המחיר צמוד לממוצע 50 - אזור תמיכה אפשרי")
        if vol_today >= avg_vol20 * 1.3:
            near_ma50_pts += 5
            reasons.append("צמידות לממוצע 50 מלווה בנפח מסחר גבוה - הגנה על תמיכה")
    score += near_ma50_pts

    # --- 3. Bollinger setup (10 pts) ----------------------------------------
    upper, mid, lower, width = bollinger_bands(close)
    bb_pts = 0
    width_percentile = (width.iloc[-1] <= width.rolling(120).quantile(0.2).iloc[-1])
    if width_percentile:
        bb_pts += 6
        reasons.append("רצועות בולינגר צרות (סקוויז) - ייתכן פריצה קרובה")
    if last_close <= lower.iloc[-1] * 1.02 and last_close > ma200.iloc[-1]:
        bb_pts += 4
        reasons.append("המחיר נוגע ברצועה התחתונה בתוך מגמת עלייה כללית - הזדמנות קנייה אפשרית")
    score += min(bb_pts, 10)

    # --- 4. Bullish candlestick (10 pts) ------------------------------------
    candle_hits = detect_bullish_candle(df)
    if candle_hits:
        score += 10
        reasons.append("זוהה נר חיובי: " + ", ".join(candle_hits))

    # --- 5. Unusual volume day (10 pts) -------------------------------------
    vol_pts = 0
    if avg_vol20 > 0 and vol_today >= avg_vol20 * VOLUME_SPIKE_MULT:
        vol_pts += 7
        reasons.append(f"נפח מסחר חריג היום (פי {vol_today / avg_vol20:.1f} מהממוצע) - כניסת כסף גדול")
        day_range = high.iloc[-1] - low.iloc[-1]
        if day_range > 0 and (last_close - low.iloc[-1]) / day_range >= 0.7:
            vol_pts += 3
            reasons.append("סגירה קרוב לשיא היום עם נפח חריג - סימן להגנה על תמיכה/קנייה מוסדית")
    score += vol_pts

    # --- 6. RSI (10 pts) -----------------------------------------------------
    rsi_val = rsi(close).iloc[-1]
    rsi_pts = 0
    if 50 <= rsi_val <= 70:
        rsi_pts = 10
        reasons.append(f"RSI={rsi_val:.0f} - מומנטום חיובי בריא (לא קניית יתר)")
    elif 40 <= rsi_val < 50:
        rsi_pts = 5
        reasons.append(f"RSI={rsi_val:.0f} - ניטרלי, אין עדיין אישור מומנטום חזק")
    elif rsi_val > 70:
        rsi_pts = 3
        reasons.append(f"RSI={rsi_val:.0f} - קניית יתר, זהירות מתיקון קצר טווח")
    else:
        reasons.append(f"RSI={rsi_val:.0f} - חלש")
    score += rsi_pts

    # --- 7. MACD (10 pts) -----------------------------------------------------
    macd_line, signal_line, hist = macd(close)
    macd_pts = 0
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_pts += 6
        reasons.append("MACD מעל קו האיתות - מגמה חיובית")
        if hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3]:
            macd_pts += 4
            reasons.append("היסטוגרמת MACD מתחזקת - האצת מומנטום")
    score += macd_pts

    # --- 8. Sector leadership (10 pts) ----------------------------------------
    sector_pts = 0
    etf = SECTOR_ETFS.get(sector)
    sector_rank = None
    if etf and etf in sector_leaderboard:
        info = sector_leaderboard[etf]
        sector_rank = info["rank"]
        n_sectors = len(sector_leaderboard)
        if sector_rank <= max(1, n_sectors // 3):
            sector_pts += 10
            reasons.append(f"הסקטור ({sector}) מוביל יחסית לשוק (דירוג {sector_rank}/{n_sectors})")
        elif sector_rank <= n_sectors * 2 // 3:
            sector_pts += 5
            reasons.append(f"הסקטור ({sector}) בביצועים ממוצעים (דירוג {sector_rank}/{n_sectors})")
        else:
            reasons.append(f"הסקטור ({sector}) חלש יחסית לשוק (דירוג {sector_rank}/{n_sectors})")
    score += sector_pts

    # --- 9. Intermarket regime alignment (5 pts) -------------------------------
    macro_pts = 0
    if sector in regime.get("favored_sectors", []):
        macro_pts = 5
        reasons.append("הסקטור מועדף בהתאם למשטר האינטרמרקט הנוכחי")
    score += macro_pts

    # --- Stop loss & price target -----------------------------------------
    recent_low = low.rolling(BREAKOUT_LOOKBACK).min().iloc[-1]
    stop_loss = min(recent_low, ma50.iloc[-1]) * 0.98  # small buffer below nearest support
    risk = last_close - stop_loss
    target = last_close + max(risk * 2.5, (week52_high - last_close) * 0.5)
    if week52_high > last_close:
        target = max(target, week52_high)
    reward = target - last_close
    rr_ratio = reward / risk if risk > 0 else np.nan

    return {
        "Ticker": ticker,
        "Sector": sector,
        "Score": round(score, 1),
        "Price": round(last_close, 2),
        "StopLoss": round(stop_loss, 2),
        "Target": round(target, 2),
        "R:R": round(rr_ratio, 2) if not np.isnan(rr_ratio) else None,
        "RSI": round(rsi_val, 1),
        "SectorRank": sector_rank,
        "Reasons": reasons,
    }


# ---------------------------------------------------------------------------
# MAIN SCAN
# ---------------------------------------------------------------------------

def run_scan(tickers, top_n=None):
    print("Fetching intermarket regime (bonds/stocks/commodities/dollar)...")
    regime = get_intermarket_regime()
    print("Regime:", regime["description"])

    print("Building sector relative-strength leaderboard...")
    sector_leaderboard = get_sector_leaderboard()

    results = []
    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i}/{len(tickers)}] scanning {ticker}...", end="\r")
        try:
            df = fetch_history(ticker)
            if df is None:
                continue
            t = yf.Ticker(ticker)
            sector = get_sector(t)
            res = score_stock(ticker, df, sector, sector_leaderboard, regime)
            results.append(res)
        except Exception as e:
            print(f"\n  skipped {ticker}: {e}")
            continue

    print()  # newline after progress
    if not results:
        print("No results.")
        return

    df_out = pd.DataFrame(results).sort_values("Score", ascending=False)
    if top_n:
        df_out = df_out.head(top_n)

    # console table (without the long Reasons column for readability)
    display_cols = ["Ticker", "Score", "Sector", "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]
    print(df_out[display_cols].to_string(index=False))

    # full CSV including reasons
    export_df = df_out.copy()
    export_df["Reasons"] = export_df["Reasons"].apply(lambda r: " | ".join(r))
    export_df.to_csv("screener_results.csv", index=False, encoding="utf-8-sig")
    print("\nSaved full results (with explanations) to screener_results.csv")

    # print top 5 with full reasoning to console
    print("\n=== טופ 5 - הסבר מלא ===")
    for _, row in df_out.head(5).iterrows():
        print(f"\n{row['Ticker']}  |  ציון: {row['Score']}  |  סקטור: {row['Sector']}")
        print(f"  מחיר: {row['Price']}  סטופ לוס: {row['StopLoss']}  יעד: {row['Target']}  R:R: {row['R:R']}")
        for r in row["Reasons"]:
            print(f"   - {r}")


def parse_args():
    p = argparse.ArgumentParser(description="Murphy-principles stock screener")
    p.add_argument("tickers", nargs="*", help="Ticker symbols to scan (default: S&P 500)")
    p.add_argument("--file", help="Path to a text file with one ticker per line")
    p.add_argument("--top", type=int, default=None, help="Only show/save top N results")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.file:
        with open(args.file) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_sp500_tickers()

    run_scan(tickers, top_n=args.top)
