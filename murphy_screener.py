"""
Murphy Screener — core engine
==============================
A stock SCREENER (not an auto-trader) built on the principles from
John Murphy's "Technical Analysis of the Financial Markets" and
"Intermarket Analysis", combined with sector relative strength and
candlestick confirmation (Nison).

The engine scores each stock 0-100 and explains, in plain English, why
it scored the way it did. It never places trades — you take it from
here.

REQUIREMENTS (run locally, not in a sandboxed/offline environment):
    pip install yfinance pandas numpy

CLI USAGE:
    python murphy_screener.py                     # scans the bundled S&P 500 list
    python murphy_screener.py AAPL MSFT NVDA       # scans just these tickers
    python murphy_screener.py --file mylist.txt    # one ticker per line
    python murphy_screener.py --top 30             # show only top 30 by score
"""

import os
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

LOOKBACK_DAYS = 400          # trading days of history to pull (covers 52w + 200MA warmup)
VOLUME_SPIKE_MULT = 2.0      # today's volume vs 20d avg volume to count as "unusual" (scoring bonus)
RECENT_VOLUME_SPIKE_MULT = 1.5   # today OR yesterday's volume vs 20d avg — a separate, more sensitive flag/filter
NEAR_MA50_PCT = 0.03         # "hugging the 50MA" = within 3%
BREAKOUT_LOOKBACK = 20       # bars used to define "recent swing low" for stop-loss

from sp_universe_data import SP500_DATA, SP400_DATA, SP600_DATA, EXTRA_TICKERS_DATA

# Merge all universes into one lookup (ticker -> (name, sector)).
# If a ticker somehow appears in more than one list, the S&P 500 entry wins.
ALL_UNIVERSE_DATA = {**SP600_DATA, **SP400_DATA, **EXTRA_TICKERS_DATA, **SP500_DATA}

# Common ETF tickers — used to classify a manually-entered ticker as an ETF
# rather than an individual stock (index/sector/commodity/bond funds, etc.)
KNOWN_ETFS = {
    "SPY", "VOO", "IVV", "QQQ", "DIA", "IWM", "IWB", "IWV", "VTI", "VT", "VXUS",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC",
    "GLD", "SLV", "GDX", "GDXJ", "USO", "UNG", "DBC", "DBA", "PDBC",
    "TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG", "TIP", "UUP", "FXE",
    "ARKK", "ARKG", "ARKW", "SOXX", "SMH", "XBI", "IBB", "KRE", "XOP", "XME",
    "VNQ", "IYR", "EFA", "EEM", "VWO", "FXI", "EWJ", "EWZ", "HYD",
    "NASA",  # Tema Space Innovators ETF — not the space agency, not a stock
}


# GICS sector -> representative SPDR sector ETF, used for relative-strength ranking
SECTOR_ETFS = {
    "Information Technology": "XLK",
    "Technology": "XLK",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Cyclical": "XLY",
    "Consumer Staples": "XLP",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Telecommunication Services": "XLC",
    "Communication Services": "XLC",
}

# Intermarket regime proxies (Murphy's four-market model)
INTERMARKET_TICKERS = {
    "Stocks": "SPY",
    "Bonds": "TLT",     # long-term treasuries -> proxy for interest-rate direction (inverse of yields)
    "Commodities": "DBC",
    "Dollar": "UUP",
}

BENCHMARK = "SPY"

# Live market snapshot: FX, individual commodities, bond proxy — shown on the
# dashboard home screen as plain price + daily % change (not part of scoring).
MARKET_SNAPSHOT_TICKERS = {
    "USD/ILS": "ILS=X",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Oil (WTI)": "CL=F",
    "Bonds (TLT)": "TLT",
}


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


def fetch_recent_quote(ticker, period_days=40):
    """Lightweight fetch for just the latest price + day-over-day change.
    Unlike fetch_history (which requires 210+ rows for 50/200-day MA and
    52-week calculations), this only needs 2 rows — used for quick live
    quotes like the market snapshot, where requesting a short window but
    then rejecting it for being 'too short' would always return nothing."""
    end = dt.date.today()
    start = end - dt.timedelta(days=int(period_days * 1.6))
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 2:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    return df


def get_market_snapshot():
    """Fetch live price + today's % change for FX/commodities/bond proxy
    tickers, for display on the dashboard home screen."""
    snapshot = {}
    for label, ticker in MARKET_SNAPSHOT_TICKERS.items():
        df = fetch_recent_quote(ticker)
        if df is None or len(df) < 2:
            snapshot[label] = {"ticker": ticker, "price": None, "day_change_pct": None}
            continue
        close = df["Close"]
        price = float(close.iloc[-1])
        day_change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
        snapshot[label] = {"ticker": ticker, "price": price, "day_change_pct": day_change_pct}
    return snapshot


def get_normalized_comparison(tickers, lookback=252):
    """Build a normalized (rebased to 100) comparison DataFrame for an
    arbitrary set of tickers, for a multi-line chart (e.g. SPY vs.
    commodities/bonds/each sector). `tickers` is a dict label -> ticker.
    Returns a DataFrame indexed by date, one column per label that had
    enough data, or None if nothing could be built."""
    series = {}
    for label, ticker in tickers.items():
        df = fetch_history(ticker, period_days=max(lookback + 30, LOOKBACK_DAYS))
        if df is None:
            continue
        close = df["Close"].tail(lookback)
        series[label] = close
    if not series:
        return None
    combined = pd.DataFrame(series).dropna()
    if combined.empty:
        return None
    normalized = combined / combined.iloc[0] * 100
    return normalized


UNIVERSE_MAP = {
    "sp500": SP500_DATA,
    "sp400": SP400_DATA,
    "sp600": SP600_DATA,
    "watchlist": EXTRA_TICKERS_DATA,
}


def get_universe_tickers(universe="sp500", n=None):
    """Return ticker symbols for a given universe.
    universe: "sp500" | "sp400" | "sp600" | "watchlist" (curated extra ADRs/tickers)
              | "all" (large + mid + small cap combined)
    Pass n to get only the first n tickers (quick partial scan); omit n for the full list.
    """
    if universe == "all":
        all_tickers = list(SP500_DATA.keys()) + list(SP400_DATA.keys()) + list(SP600_DATA.keys())
    else:
        table = UNIVERSE_MAP.get(universe, SP500_DATA)
        all_tickers = list(table.keys())
    if n is None:
        return all_tickers
    n = max(1, min(int(n), len(all_tickers)))
    return all_tickers[:n]


def get_sp500_tickers(n=None):
    """Backward-compatible alias for get_universe_tickers('sp500', n)."""
    return get_universe_tickers("sp500", n)


def get_sector(ticker):
    """Look up sector for a ticker. Prefers the embedded S&P 500/400/600 map
    (fast, free, no rate limits); falls back to a live yfinance lookup if the
    ticker isn't in that map (e.g. a non-US-index symbol or an ETF)."""
    if ticker in ALL_UNIVERSE_DATA:
        return ALL_UNIVERSE_DATA[ticker][1]

    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


def is_etf(ticker):
    """Classify a ticker as an ETF or an individual stock. Any ticker found
    in our S&P 500/400/600 constituent data is by definition a stock. For
    anything else, check a known-ETF list first (fast, no API call), then
    fall back to a live yfinance quoteType lookup."""
    if ticker in ALL_UNIVERSE_DATA:
        return False
    if ticker in KNOWN_ETFS:
        return True
    try:
        info = yf.Ticker(ticker).info
        return info.get("quoteType", "").upper() == "ETF"
    except Exception:
        return False


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


def compute_beta(stock_close, spy_close, window=252):
    """Beta of the stock vs. SPY, computed directly from daily returns
    (covariance / variance) over the trailing `window` trading days —
    no dependency on yfinance's often-stale/missing .info['beta'] field."""
    stock_ret = stock_close.pct_change().dropna()
    spy_ret = spy_close.pct_change().dropna()
    combined = pd.concat([stock_ret, spy_ret], axis=1, join="inner").tail(window)
    combined.columns = ["stock", "spy"]
    if len(combined) < 30:
        return np.nan
    var = combined["spy"].var()
    if not var or np.isnan(var):
        return np.nan
    return float(combined["stock"].cov(combined["spy"]) / var)


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
            hits.append("Hammer (bullish reversal at a downtrend low)")
        if is_bullish_engulfing(o, h, l, c):
            hits.append("Bullish Engulfing pattern")
        if is_piercing_line(o, h, l, c):
            hits.append("Piercing Line pattern")
        if is_morning_star(o, h, l, c):
            hits.append("Morning Star pattern")
    except Exception:
        pass
    return hits


# ---------------------------------------------------------------------------
# INTERMARKET REGIME (Murphy's Intermarket Analysis)
# ---------------------------------------------------------------------------

def trend_direction(close, window=60, compare_bars=20, threshold=0.005):
    """Slope-based trend: is the N-day SMA rising or falling, comparing its
    current value to `compare_bars` trading days ago? Returns (direction,
    pct_change) where pct_change is the % move of the MA over that window —
    shown alongside the label so 'Flat' is legible rather than a mystery
    (e.g. a genuinely quiet market can show +/-0.2% and correctly read Flat)."""
    ma = sma(close, window)
    valid = ma.dropna()
    if len(valid) < compare_bars + 1:
        return "flat", 0.0
    recent = valid.iloc[-1]
    prior = valid.iloc[-(compare_bars + 1)]
    pct_change = (recent / prior - 1) * 100
    if pct_change > threshold * 100:
        return "up", pct_change
    elif pct_change < -threshold * 100:
        return "down", pct_change
    return "flat", pct_change


def get_intermarket_regime():
    """Classify the macro regime using bonds/stocks/commodities/dollar trends,
    per Murphy's four-market model + Pring's six-stage business cycle map."""
    trends = {}
    trends_pct = {}
    for name, ticker in INTERMARKET_TICKERS.items():
        df = fetch_history(ticker, period_days=250)
        if df is None:
            trends[name] = "unknown"
            trends_pct[name] = None
        else:
            direction, pct_change = trend_direction(df["Close"])
            trends[name] = direction
            trends_pct[name] = round(pct_change, 2)

    bonds, stocks, commodities, dollar = (trends.get(k, "unknown") for k in
                                           ["Bonds", "Stocks", "Commodities", "Dollar"])

    # Bonds (TLT) rising == interest rates falling; bonds falling == rates rising
    if commodities == "up" and bonds == "down":
        regime = ("Early/mid inflationary regime: commodities rising, bonds falling (rates rising) — "
                   "favor commodities/energy, caution on rate-sensitive stocks")
        favored = ["Energy", "Materials", "Basic Materials"]
    elif commodities == "down" and bonds == "up":
        regime = ("Disinflationary/slowdown regime: commodities falling, bonds rising (rates falling) — "
                   "favor bonds and defensive stocks")
        favored = ["Utilities", "Consumer Staples", "Consumer Defensive", "Health Care", "Healthcare"]
    elif stocks == "up" and bonds == "up":
        regime = "Healthy early expansion: both stocks and bonds rising — constructive for growth stocks"
        favored = ["Information Technology", "Technology", "Financials", "Financial Services", "Consumer Discretionary"]
    elif stocks == "down" and commodities == "down" and bonds == "down":
        regime = "Stage 6 (everything falling) — cash is king, increased caution across all positions"
        favored = []
    else:
        regime = f"Mixed / no clear signal (stocks={stocks}, bonds={bonds}, commodities={commodities}, dollar={dollar})"
        favored = []

    return {"trends": trends, "trends_pct": trends_pct, "description": regime, "favored_sectors": favored}


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
    etf_to_sector = {}
    for sector, etf in SECTOR_ETFS.items():
        etf_to_sector.setdefault(etf, sector)
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

        last_price = float(close.iloc[-1])
        day_change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else np.nan

        results[etf] = {
            "1w": rel_perf(5),
            "1m": rel_perf(21),
            "3m": rel_perf(63),
            "12m": rel_perf(252),
            "price": last_price,
            "day_change_pct": day_change_pct,
        }

    # rank sectors by average of 1m + 3m relative strength (medium-term leadership)
    ranked = sorted(results.items(), key=lambda kv: np.nanmean([kv[1]["1m"], kv[1]["3m"]]), reverse=True)

    leaderboard = {}
    for rank, (etf, perf) in enumerate(ranked, start=1):
        leaderboard[etf] = {"rank": rank, "sector": etf_to_sector[etf], **perf}
    return leaderboard


def summarize_sector_strength(sector_leaderboard):
    """Split the sector leaderboard into 'showing strength' (top third by
    1m/3m relative performance vs. SPY) and 'showing weakness' (bottom
    third), per Murphy's relative-strength / sector-rotation approach.
    Returns (strong_list, weak_list), each a list of (sector_name, etf) tuples
    ordered from strongest/weakest outward."""
    if not sector_leaderboard:
        return [], []
    ranked = sorted(sector_leaderboard.items(), key=lambda kv: kv[1]["rank"])
    n = len(ranked)
    top_cut = max(1, n // 3)
    bottom_cut = n - max(1, n // 3)
    strong = [(info["sector"], etf) for etf, info in ranked[:top_cut]]
    weak = [(info["sector"], etf) for etf, info in ranked[bottom_cut:]]
    return strong, weak


def strong_sector_etfs(sector_leaderboard):
    """Return the set of ETF tickers representing the currently-strong
    sectors (top third of the leaderboard). Comparing by ETF ticker (not
    sector name string) sidesteps GICS naming variants like 'Telecommunication
    Services' vs 'Communication Services' referring to the same sector."""
    strong, _ = summarize_sector_strength(sector_leaderboard)
    return {etf for _, etf in strong}


def stock_is_in_strong_sector(sector, sector_leaderboard, strong_etfs):
    """True if this stock's sector maps to an ETF currently in the strong group."""
    etf = SECTOR_ETFS.get(sector)
    return etf is not None and etf in strong_etfs


def get_relative_strength_series(ticker_df, spy_df, lookback=126):
    """Build a normalized (rebased to 100) comparison series for a stock vs
    SPY over the last `lookback` trading days, for a relative-strength chart.
    Returns a DataFrame indexed by date with 'Stock' and 'SPY' columns, or
    None if there isn't enough overlapping data."""
    if ticker_df is None or spy_df is None:
        return None
    stock_close = ticker_df["Close"].tail(lookback)
    spy_close = spy_df["Close"].tail(lookback)
    combined = pd.DataFrame({"Stock": stock_close, "SPY": spy_close}).dropna()
    if combined.empty:
        return None
    normalized = combined / combined.iloc[0] * 100
    return normalized


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def score_stock(ticker, df, sector, sector_leaderboard, regime, is_etf=False, spy_close=None):
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    last_close = close.iloc[-1]
    reasons = []
    score = 0

    beta = compute_beta(close, spy_close) if spy_close is not None else np.nan
    if not np.isnan(beta):
        if beta >= 1:
            reasons.append(f"Beta={beta:.2f} — moves at least as much as the market (higher-beta profile)")
        else:
            reasons.append(f"Beta={beta:.2f} — moves less than the market (lower-beta/defensive profile)")

    # --- 1. 52-week trend template (25 pts) ---------------------------------
    ma50 = sma(close, 50)
    ma200 = sma(close, 200)
    week52_high = close.rolling(252).max().iloc[-1]
    price_52w_ago = close.iloc[-252] if len(close) >= 252 else close.iloc[0]

    trend_pts = 0
    if last_close > price_52w_ago:
        trend_pts += 8
        reasons.append("Price is above where it was 52 weeks ago (positive yearly trend)")
    if last_close > ma50.iloc[-1] and last_close > ma200.iloc[-1]:
        trend_pts += 10
        reasons.append("Price is above both the 50-day and 200-day moving averages (confirmed uptrend)")
    if ma50.iloc[-1] > ma200.iloc[-1]:
        trend_pts += 4
        reasons.append("50-day MA is above the 200-day MA (golden-cross structure)")
    if last_close >= week52_high * 0.75:
        trend_pts += 3
        reasons.append("Price is within 25% of its 52-week high")
    score += min(trend_pts, 25)

    # --- 2. Near-MA50 pullback opportunity on volume (10 pts) ---------------
    near_ma50_pts = 0
    support_signal = False
    dist_from_ma50 = abs(last_close - ma50.iloc[-1]) / ma50.iloc[-1]
    avg_vol20 = vol.rolling(20).mean().iloc[-1]
    vol_today = vol.iloc[-1]
    vol_yesterday = vol.iloc[-2] if len(vol) >= 2 else np.nan

    # Recent volume spike (today OR yesterday >= 1.5x the 20-day average) —
    # a standalone, more sensitive signal separate from the scoring bonus below.
    ratio_today = vol_today / avg_vol20 if avg_vol20 > 0 else np.nan
    ratio_yesterday = vol_yesterday / avg_vol20 if avg_vol20 > 0 and not np.isnan(vol_yesterday) else np.nan
    if np.isnan(ratio_yesterday) or (not np.isnan(ratio_today) and ratio_today >= ratio_yesterday):
        volume_spike_ratio, volume_spike_day = ratio_today, "Today"
    else:
        volume_spike_ratio, volume_spike_day = ratio_yesterday, "Yesterday"
    volume_spike_flag = (not np.isnan(volume_spike_ratio)) and volume_spike_ratio >= RECENT_VOLUME_SPIKE_MULT
    if volume_spike_flag:
        reasons.append(f"Volume spike: {volume_spike_ratio:.1f}x the 20-day average volume "
                        f"({volume_spike_day}) — meets the 1.5x threshold, a strong potential-move indicator")

    if dist_from_ma50 <= NEAR_MA50_PCT and last_close >= ma50.iloc[-1] * 0.98:
        near_ma50_pts += 5
        support_signal = True
        reasons.append("Price is hugging the 50-day MA — a possible support zone")
        if vol_today >= avg_vol20 * 1.3:
            near_ma50_pts += 5
            reasons.append("...and that 50-MA test is accompanied by elevated volume (support defense)")
    score += near_ma50_pts

    # --- 3. Bollinger setup (10 pts) ----------------------------------------
    upper, mid, lower, width = bollinger_bands(close)
    bb_pts = 0
    squeeze_signal = False
    width_percentile = (width.iloc[-1] <= width.rolling(120).quantile(0.2).iloc[-1])
    if width_percentile:
        bb_pts += 6
        squeeze_signal = True
        reasons.append("Bollinger Bands are unusually narrow (squeeze) — a breakout may be brewing")
    if last_close <= lower.iloc[-1] * 1.02 and last_close > ma200.iloc[-1]:
        bb_pts += 4
        support_signal = True
        reasons.append("Price is touching the lower Bollinger Band within an overall uptrend — possible buy zone")
    score += min(bb_pts, 10)

    # --- 4. Bullish candlestick (10 pts) ------------------------------------
    candle_hits = detect_bullish_candle(df)
    candle_signal = bool(candle_hits)
    if candle_hits:
        score += 10
        reasons.append("Bullish candlestick detected: " + ", ".join(candle_hits))

    # --- 5. Unusual volume day (10 pts) -------------------------------------
    vol_pts = 0
    volume_signal = False
    if avg_vol20 > 0 and vol_today >= avg_vol20 * VOLUME_SPIKE_MULT:
        vol_pts += 7
        volume_signal = True
        reasons.append(f"Unusual volume today ({vol_today / avg_vol20:.1f}x the 20-day average) — possible large money flow")
        day_range = high.iloc[-1] - low.iloc[-1]
        if day_range > 0 and (last_close - low.iloc[-1]) / day_range >= 0.7:
            vol_pts += 3
            reasons.append("...closed near the day's high on that unusual volume — sign of support defense / institutional buying")
    score += vol_pts

    # --- 6. RSI (10 pts) -----------------------------------------------------
    rsi_val = rsi(close).iloc[-1]
    rsi_pts = 0
    if 50 <= rsi_val <= 70:
        rsi_pts = 10
        reasons.append(f"RSI={rsi_val:.0f} — healthy bullish momentum, not overbought")
    elif 40 <= rsi_val < 50:
        rsi_pts = 5
        reasons.append(f"RSI={rsi_val:.0f} — neutral, no strong momentum confirmation yet")
    elif rsi_val > 70:
        rsi_pts = 3
        reasons.append(f"RSI={rsi_val:.0f} — overbought, watch for a short-term pullback")
    else:
        reasons.append(f"RSI={rsi_val:.0f} — weak")
    score += rsi_pts

    # --- 7. MACD (10 pts) -----------------------------------------------------
    macd_line, signal_line, hist = macd(close)
    macd_pts = 0
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        macd_pts += 6
        reasons.append("MACD is above its signal line — positive momentum")
        if hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3]:
            macd_pts += 4
            reasons.append("MACD histogram is expanding — momentum is accelerating")
    score += macd_pts

    # --- 8. Sector leadership (10 pts) — stocks only ---------------------------
    sector_pts = 0
    sector_rank = None
    if is_etf:
        reasons.append("Sector-leadership and macro-regime scoring not applicable to ETFs "
                        "(score is out of 85, rescaled to 100)")
    else:
        etf_for_sector = SECTOR_ETFS.get(sector)
        if etf_for_sector and etf_for_sector in sector_leaderboard:
            info = sector_leaderboard[etf_for_sector]
            sector_rank = info["rank"]
            n_sectors = len(sector_leaderboard)
            if sector_rank <= max(1, n_sectors // 3):
                sector_pts += 10
                reasons.append(f"Sector ({sector}) is a market leader right now (rank {sector_rank}/{n_sectors})")
            elif sector_rank <= n_sectors * 2 // 3:
                sector_pts += 5
                reasons.append(f"Sector ({sector}) is performing in-line with the market (rank {sector_rank}/{n_sectors})")
            else:
                reasons.append(f"Sector ({sector}) is lagging the market (rank {sector_rank}/{n_sectors})")
        score += sector_pts

    # --- 9. Intermarket regime alignment (5 pts) — stocks only -----------------
    macro_pts = 0
    if not is_etf and sector in regime.get("favored_sectors", []):
        macro_pts = 5
        reasons.append("Sector is favored under the current intermarket regime")
    score += macro_pts

    if is_etf:
        # Rescale the 0-85 possible ETF score back onto a 0-100 scale so ETF
        # and stock scores stay visually comparable.
        score = score * 100 / 85

    # --- Stop loss & price target -----------------------------------------
    recent_low = low.rolling(BREAKOUT_LOOKBACK).min().iloc[-1]
    stop_loss = min(recent_low, ma50.iloc[-1]) * 0.98  # small buffer below nearest support
    risk = last_close - stop_loss
    target = last_close + max(risk * 2.5, (week52_high - last_close) * 0.5)
    if week52_high > last_close:
        target = max(target, week52_high)
    reward = target - last_close
    rr_ratio = reward / risk if risk > 0 else np.nan

    # --- Actionable setup classification -----------------------------------
    # "Buy Zone": a concrete technical trigger is present right now (price at
    # a support level, a bullish candle, or unusual volume).
    # "Watchlist": no trigger yet, but the trend is strong or a squeeze is
    # forming — worth monitoring over the next few days for a trigger.
    # "No Signal": generic uptrend only, nothing actionable — filtered out
    # by default so the list stays focused on real candidates.
    if support_signal or candle_signal or volume_signal or volume_spike_flag:
        setup = "Buy Zone"
        reasons.append("SETUP: Buy Zone — a concrete entry trigger is present right now "
                        "(support test, bullish candle, and/or unusual volume)")
    elif squeeze_signal or trend_pts >= 18:
        setup = "Watchlist"
        reasons.append("SETUP: Watchlist — strong trend/setup forming but no confirmed entry trigger yet; "
                        "monitor over the next few days for a support test, candle, or volume confirmation")
    else:
        setup = "No Signal"
        reasons.append("SETUP: No Signal — generic trend only, no actionable entry trigger found")

    return {
        "Ticker": ticker,
        "AssetType": "ETF" if is_etf else "Stock",
        "Sector": "ETF" if is_etf else sector,
        "Setup": setup,
        "Beta": round(beta, 2) if not np.isnan(beta) else None,
        "VolumeSpike": bool(volume_spike_flag),
        "VolumeSpikeRatio": round(float(volume_spike_ratio), 2) if not np.isnan(volume_spike_ratio) else None,
        "VolumeSpikeDay": volume_spike_day if volume_spike_flag else None,
        "Score": round(score, 1),
        "Price": round(float(last_close), 2),
        "StopLoss": round(float(stop_loss), 2),
        "Target": round(float(target), 2),
        "R:R": round(float(rr_ratio), 2) if not np.isnan(rr_ratio) else None,
        "RSI": round(float(rsi_val), 1),
        "SectorRank": sector_rank,
        "Reasons": reasons,
    }


# ---------------------------------------------------------------------------
# MAIN SCAN (CLI)
# ---------------------------------------------------------------------------

def _fmt_price_cols(df):
    """Format Price/StopLoss/Target/R:R as clean 2-decimal strings for display."""
    out = df.copy()
    for col in ["Price", "StopLoss", "Target", "R:R"]:
        out[col] = out[col].apply(lambda v: f"{v:.2f}" if pd.notnull(v) else "")
    return out


SETUP_SORT_ORDER = {"Buy Zone": 0, "Watchlist": 1, "No Signal": 2}


def run_scan(tickers, top_n=None, only_strong_sectors=True, min_beta=1.0, only_actionable=True,
             require_volume_spike=False):
    print("Fetching intermarket regime (bonds/stocks/commodities/dollar)...")
    regime = get_intermarket_regime()
    print("Regime:", regime["description"])

    print("Building sector relative-strength leaderboard...")
    sector_leaderboard = get_sector_leaderboard()

    strong, weak = summarize_sector_strength(sector_leaderboard)
    strong_etfs = strong_sector_etfs(sector_leaderboard)
    print("\nSectors showing STRENGTH:", ", ".join(f"{s} ({e})" for s, e in strong) or "n/a")
    print("Sectors showing WEAKNESS:", ", ".join(f"{s} ({e})" for s, e in weak) or "n/a")
    if only_strong_sectors and strong_etfs:
        print("(Stock results are filtered to strong sectors only — pass only_strong_sectors=False to disable)")
    if min_beta is not None:
        print(f"(Stocks below beta {min_beta} are filtered out — pass min_beta=None to disable)")
    if only_actionable:
        print("(Only 'Buy Zone' / 'Watchlist' setups are shown — pass only_actionable=False to include 'No Signal')")
    if require_volume_spike:
        print(f"(Only stocks with volume >= {RECENT_VOLUME_SPIKE_MULT}x average today or yesterday are shown)")

    spy_df = fetch_history(BENCHMARK)
    spy_close = spy_df["Close"] if spy_df is not None else None

    stock_results, etf_results = [], []
    skipped_weak_sector = skipped_beta = skipped_no_signal = skipped_no_vol_spike = 0
    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i}/{len(tickers)}] scanning {ticker}...", end="\r")
        try:
            df = fetch_history(ticker)
            if df is None:
                continue
            etf_flag = is_etf(ticker)
            sector = "ETF" if etf_flag else get_sector(ticker)
            if not etf_flag and only_strong_sectors and strong_etfs:
                if not stock_is_in_strong_sector(sector, sector_leaderboard, strong_etfs):
                    skipped_weak_sector += 1
                    continue
            res = score_stock(ticker, df, sector, sector_leaderboard, regime, is_etf=etf_flag, spy_close=spy_close)
            if not etf_flag:
                if min_beta is not None and res["Beta"] is not None and res["Beta"] < min_beta:
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
            print(f"\n  skipped {ticker}: {e}")
            continue

    print()  # newline after progress
    if only_strong_sectors and skipped_weak_sector:
        print(f"Skipped {skipped_weak_sector} stocks outside the strong sectors.")
    if min_beta is not None and skipped_beta:
        print(f"Skipped {skipped_beta} stocks with beta below {min_beta}.")
    if only_actionable and skipped_no_signal:
        print(f"Skipped {skipped_no_signal} stocks with no actionable setup.")
    if require_volume_spike and skipped_no_vol_spike:
        print(f"Skipped {skipped_no_vol_spike} stocks without a {RECENT_VOLUME_SPIKE_MULT}x+ volume spike.")
    if not stock_results and not etf_results:
        print("No results.")
        return

    display_cols = ["Ticker", "Score", "Setup", "Sector", "Beta", "VolumeSpikeRatio", "VolumeSpikeDay",
                     "Price", "StopLoss", "Target", "R:R", "RSI", "SectorRank"]

    def sort_key(df_):
        return df_.assign(_s=df_["Setup"].map(SETUP_SORT_ORDER).fillna(9)).sort_values(
            ["_s", "Score"], ascending=[True, False]).drop(columns="_s")

    def show_and_save(results, label, filename, sort_by_setup=False):
        if not results:
            return None
        df_out = pd.DataFrame(results)
        df_out = sort_key(df_out) if sort_by_setup else df_out.sort_values("Score", ascending=False)
        if top_n:
            df_out = df_out.head(top_n)
        print(f"\n=== {label} ===")
        print(_fmt_price_cols(df_out)[display_cols].to_string(index=False))
        export_df = df_out.copy()
        export_df["Reasons"] = export_df["Reasons"].apply(lambda r: " | ".join(r))
        export_df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"Saved full results (with explanations) to {filename}")
        return df_out

    stocks_df = show_and_save(stock_results, "STOCKS", "screener_results_stocks.csv", sort_by_setup=True)
    etfs_df = show_and_save(etf_results, "ETFs", "screener_results_etfs.csv")

    if stocks_df is not None:
        print("\n=== Top 5 stocks — full explanation ===")
        for _, row in stocks_df.head(5).iterrows():
            print(f"\n{row['Ticker']}  |  Score: {row['Score']}  |  Setup: {row['Setup']}  |  Sector: {row['Sector']}")
            print(f"  Price: {row['Price']:.2f}  Stop-loss: {row['StopLoss']:.2f}  "
                  f"Target: {row['Target']:.2f}  R:R: {row['R:R']}  Beta: {row['Beta']}")
            for r in row["Reasons"]:
                print(f"   - {r}")


def parse_args():
    p = argparse.ArgumentParser(description="Murphy-principles stock/ETF screener")
    p.add_argument("tickers", nargs="*", help="Ticker symbols to scan (default: universe selected via --universe)")
    p.add_argument("--file", help="Path to a text file with one ticker per line")
    p.add_argument("--universe", choices=["sp500", "sp400", "sp600", "all"], default="sp500",
                    help="Which built-in universe to scan when no explicit tickers are given "
                         "(sp500=large-cap, sp400=mid-cap, sp600=small-cap, all=combined). Default: sp500")
    p.add_argument("--count", type=int, default=None,
                    help="Only scan the first N tickers from the chosen universe (default: all of them)")
    p.add_argument("--top", type=int, default=None, help="Only show/save top N results per list (stocks/ETFs)")
    p.add_argument("--all-sectors", action="store_true",
                    help="Include stocks from every sector, not just the currently-strong ones "
                         "(by default, stock results are filtered to strong sectors only)")
    p.add_argument("--min-beta", type=float, default=1.0,
                    help="Minimum beta (vs. SPY) for a stock to be included. Default: 1.0. "
                         "Use a negative number (e.g. -1) to disable beta filtering.")
    p.add_argument("--all-setups", action="store_true",
                    help="Include stocks with no actionable entry trigger ('No Signal'), not just "
                         "'Buy Zone' / 'Watchlist' (by default, 'No Signal' stocks are filtered out)")
    p.add_argument("--require-volume-spike", action="store_true",
                    help="Only include stocks whose volume today OR yesterday was at least "
                         f"{RECENT_VOLUME_SPIKE_MULT}x the 20-day average (off by default)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.file:
        with open(args.file) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_universe_tickers(args.universe, args.count)

    run_scan(tickers, top_n=args.top, only_strong_sectors=not args.all_sectors,
              min_beta=(None if args.min_beta < 0 else args.min_beta),
              only_actionable=not args.all_setups,
              require_volume_spike=args.require_volume_spike)
