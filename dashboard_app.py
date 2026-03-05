import streamlit as st
import pandas as pd
import yfinance as yf

# ==========================================
# 1. הגדרות ותצורה
# ==========================================
st.set_page_config(page_title="IBI True Profit Tracker", layout="wide", page_icon="🇺🇸")

st.markdown("""
<style>
    body {text-align: right; direction: rtl;}
    .stMetric {text-align: center; border: 1px solid #f0f2f6; padding: 15px; border-radius: 10px; background-color: white;}
    div[data-testid="stMetricValue"] {font-size: 26px; font-weight: bold; color: #0f1111;}
    div[data-testid="stMetricLabel"] {font-size: 16px; font-weight: normal; color: #555;}
    
    /* Highlight for the Real Profit Box */
    div[data-testid="stMetricValue"] > div {text-shadow: none;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. נתונים (Hardcoded Data from PDF Analysis)
# ==========================================

# יתרת מזומן דולרית מחושבת (לאחר כל הפעולות, העמלות ומגני המס ב-PDF)
CASH_BALANCE_USD = 378.45 

# סך כל ההפקדות בשקלים (Money In) - חולץ מתוך ה-PDF שלך:
# 10/12: 6300 | 14/12: 5022 | 17/12: 300 | 21/12: 2700 | 23/12: 450 | 24/12: 50
# 09/01: 3200 | 14/01: 1600 | 11/02: 1300
TOTAL_DEPOSITED_ILS = 20922.0

# התיק הנוכחי (פוזיציות פתוחות)
CURRENT_PORTFOLIO = [
    {"Symbol": "GLW",  "Qty": 16, "Buy_Price": 145.54, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "SPOT", "Qty": 7,  "Buy_Price": 528.20, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "WDC",  "Qty": 7,  "Buy_Price": 270.53, "Date": "24.02.2026", "Fee": 7.0},
]

# היסטוריית מכירות (לצורך תיעוד וחישוב עמלות מצטברות)
SOLD_HISTORY = [
    {"Symbol": "TLN", "Qty": 11, "Sell_Price": 338.51, "Buy_Price": 359.89, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "AXTI", "Qty": 95, "Sell_Price": 39.75, "Buy_Price": 40.69, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "WDC", "Qty": 8, "Sell_Price": 270.00, "Buy_Price": 270.80, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "VIAV", "Qty": 98, "Sell_Price": 29.13, "Buy_Price": 26.34, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "GLW", "Qty": 22, "Sell_Price": 152.38, "Buy_Price": 131.90, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "LOW", "Qty": 8, "Sell_Price": 274.18, "Buy_Price": 278.69, "Date": "23.02.2026", "Fee_Total": 14.0},
    {"Symbol": "PESI", "Qty": 218, "Sell_Price": 14.80, "Buy_Price": 14.83, "Date": "13.02.2026", "Fee_Total": 14.0},
    {"Symbol": "SMH", "Qty": 11, "Sell_Price": 408.00, "Buy_Price": 404.40, "Date": "13.02.2026", "Fee_Total": 14.0},
    {"Symbol": "AMTM", "Qty": 90, "Sell_Price": 31.44, "Buy_Price": 32.40, "Date": "12.02.2026", "Fee_Total": 14.0},
    {"Symbol": "WFRD", "Qty": 27, "Sell_Price": 102.46, "Buy_Price": 93.95, "Date": "10.02.2026", "Fee_Total": 14.0},
    {"Symbol": "KLAC", "Qty": 2, "Sell_Price": 1407.74, "Buy_Price": 1433.00, "Date": "01.02.2026", "Fee_Total": 14.0},
    {"Symbol": "DIS", "Qty": 40, "Sell_Price": 107.52, "Buy_Price": 105.00, "Date": "01.02.2026", "Fee_Total": 14.0},
    {"Symbol": "BARK", "Qty": 2500, "Sell_Price": 0.8501, "Buy_Price": 0.89, "Date": "01.02.2026", "Fee_Total": 14.0},
    {"Symbol": "INOD", "Qty": 45, "Sell_Price": 54.82, "Buy_Price": 56.30, "Date": "01.02.2026", "Fee_Total": 14.0},
    {"Symbol": "MP", "Qty": 59, "Sell_Price": 61.41, "Buy_Price": 59.77, "Date": "29.01.2026", "Fee_Total": 14.0},
    {"Symbol": "ALB", "Qty": 26, "Sell_Price": 177.60, "Buy_Price": 172.00, "Date": "29.01.2026", "Fee_Total": 14.0},
    {"Symbol": "SLI", "Qty": 530, "Sell_Price": 4.95, "Buy_Price": 5.39, "Date": "29.01.2026", "Fee_Total": 14.0},
    {"Symbol": "VRT", "Qty": 8, "Sell_Price": 183.00, "Buy_Price": 163.00, "Date": "27.01.2026", "Fee_Total": 14.5},
    {"Symbol": "GEV", "Qty": 2, "Sell_Price": 654.21, "Buy_Price": 700.00, "Date": "24.01.2026", "Fee_Total": 14.5},
    {"Symbol": "PLTR", "Qty": 2, "Sell_Price": 174.00, "Buy_Price": 183.36, "Date": "15.01.2026", "Fee_Total": 14.5}, 
    {"Symbol": "AMZN", "Qty": 6, "Sell_Price": 233.80, "Buy_Price": 227.00, "Date": "15.01.2026", "Fee_Total": 14.5},
    {"Symbol": "VRTX", "Qty": 5, "Sell_Price": 432.16, "Buy_Price": 444.00, "Date": "15.01.2026", "Fee_Total": 14.0},
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "OSS",  "Qty": 165, "Sell_Price": 11.95, "Buy_Price": 11.99, "Date": "13.01.2026", "Fee_Total": 14.0},
    {"Symbol": "BIFT", "Qty": 625, "Sell_Price": 3.05, "Buy_Price": 3.21,  "Date": "13.01.2026", "Fee_Total": 14.0},
]

EARNINGS_CALENDAR = {
    "GLW": "28/04/26", "SPOT": "23/04/26", "WDC": "23/04/26"
}

# ==========================================
# 3. מנוע חישובים
# ==========================================
def get_data():
    # 1. שער דולר עדכני
    try:
        usd_rate = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_rate = 3.60 # Fallback

    # 2. נתוני מניות חיות
    tickers_list = [p['Symbol'] for p in CURRENT_PORTFOLIO]
    live_data = []
    total_stock_value_usd = 0
    
    if tickers_list:
        tickers = yf.Tickers(" ".join(tickers_list))
        for item in CURRENT_PORTFOLIO:
            sym = item['Symbol']
            qty = item['Qty']
            buy_price = item['Buy_Price']
            
            try:
                t = tickers.tickers[sym]
                current_price = t.fast_info.last_price
                # חישוב שינוי יומי אמין
                hist = t.history(period="5d")
                prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else t.fast_info.previous_close
            except:
                current_price = buy_price
                prev_close = buy_price

            market_val = current_price * qty
            total_stock_value_usd += market_val
            
            # חישוב רווח/הפסד פתוח בדולרים
            unrealized_pl = (current_price - buy_price) * qty
            total_change_pct = ((current_price - buy_price) / buy_price) * 100
            
            # שינוי יומי
            day_change_usd = current_price - prev_close
            day_change_pct = (day_change_usd / prev_close) * 100

            def color(val, suffix=""):
                c = "#00c853" if val >= 0 else "#d50000"
                return f'<span style="color:{c}; font-weight:bold;">{val:,.2f}{suffix}</span>'

            live_data.append({
                "Symbol": sym,
                "Qty": qty,
                "Price ($)": f"${current_price:,.2f}",
                "Day Change": f"{color(day_change_usd, '$')} ({color(day_change_pct, '%')})",
                "Cost ($)": f"${buy_price:,.2f}",
                "Value ($)": f"${market_val:,.2f}",
                "Total P/L ($)": f"{color(unrealized_pl, '$')} ({color(total_change_pct, '%')})",
                "Next Report": EARNINGS_CALENDAR.get(sym, "-")
            })

    return pd.DataFrame(live_data), usd_rate, total_stock_value_usd

# ==========================================
# 4. ממשק משתמש (UI)
# ==========================================
st.title("IBI Portfolio Dashboard 🇺🇸")
st.caption("מציג נתונים שוטפים בדולר, ורווח סופי בשקלים (כולל השפעת שער המטבע).")

if st.button("🔄 רענן נתונים"):
    st.rerun()

with st.spinner("מבצע חישובים..."):
    df, rate, stock_val_usd = get_data()

# --- חישובים קריטיים ---

# 1. שווי התיק הנוכחי בדולר
total_equity_usd = stock_val_usd + CASH_BALANCE_USD

# 2. שווי התיק הנוכחי בשקלים (לפי השער של הרגע)
total_equity_ils = total_equity_usd * rate

# 3. רווח/הפסד *אמיתי* בשקלים (שווי נוכחי פחות מה שהופקד מהבנק)
real_profit_ils = total_equity_ils - TOTAL_DEPOSITED_ILS
real_profit_ils_pct = (real_profit_ils / TOTAL_DEPOSITED_ILS) * 100

# 4. רווח דולרי "פנימי" (רק פעילות מסחר, ללא השפעת שער)
# אנחנו משווים את השווי הדולרי הנוכחי לכמות הדולרים שהופקדו במקור (בערך)
# לצורך הפשטות, כאן נציג את זה כרווח שוקלי מתואם
dollar_performance_pct = ((total_equity_usd - (TOTAL_DEPOSITED_ILS / 3.3)) / (TOTAL_DEPOSITED_ILS / 3.3)) * 100 
# הערה: 3.3 הוא שער ממוצע גס להפקדות, רק לצורך אינדיקציה כללית לביצועי המניות עצמן

# --- תצוגת מדדים עליונה ---
st.markdown("### 🏦 תמונת מצב (Snapshot)")

# שורה ראשונה: סטטוס דולרי (שוטף)
c1, c2, c3, c4 = st.columns(4)
c1.metric("שווי תיק כולל ($)", f"${total_equity_usd:,.2f}")
c2.metric("מזומן נזיל ($)", f"${CASH_BALANCE_USD:,.2f}", help="מזומן פנוי למסחר")
c3.metric("שער דולר רציף", f"₪{rate:.3f}")
c4.metric("שווי מניות ($)", f"${stock_val_usd:,.2f}")

st.divider()

# שורה שנייה: האמת בשקלים (השורה התחתונה)
st.markdown("### ₪ השורה התחתונה (Money In vs. Money Out)")
k1, k2, k3 = st.columns(3)

k1.metric("סה״כ הופקד מהבנק (₪)", f"₪{TOTAL_DEPOSITED_ILS:,.0f}", help="סכום כל ההעברות השקליות לחשבון")
k2.metric("שווי נוכחי בשקלים (₪)", f"₪{total_equity_ils:,.0f}", help="שווי התיק הדולרי כפול השער היציג עכשיו")

real_color = "normal" if real_profit_ils >= 0 else "inverse"
k3.metric("רווח/הפסד ריאלי (₪)", f"₪{real_profit_ils:,.0f}", f"{real_profit_ils_pct:.2f}%", delta_color=real_color, 
          help="זה המספר הקובע. האם יש לך יותר או פחות שקלים ממה שהכנסת.")

st.divider()

# --- לשוניות פירוט ---
tab1, tab2 = st.tabs(["📊 תיק מניות (דולרי)", "📜 היסטוריית מכירות"])

with tab1:
    if not df.empty:
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("אין החזקות כרגע.")

with tab2:
    st.subheader("עסקאות שנסגרו (History)")
    hist_data = []
    for t in SOLD_HISTORY:
        net = (t['Sell_Price'] - t['Buy_Price']) * t['Qty'] - t.get('Fee_Total', 14)
        c = "green" if net > 0 else "red"
        hist_data.append({
            "Symbol": t['Symbol'],
            "Qty": t['Qty'],
            "Buy": f"${t['Buy_Price']}",
            "Sell": f"${t['Sell_Price']}",
            "Net P/L": f'<span style="color:{c}; font-weight:bold;">${net:,.2f}</span>',
            "Date": t['Date']
        })
    st.write(pd.DataFrame(hist_data).to_html(escape=False, index=False), unsafe_allow_html=True)
