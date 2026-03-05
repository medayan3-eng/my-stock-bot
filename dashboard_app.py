import streamlit as st
import pandas as pd
import yfinance as yf

# ==========================================
# 1. הגדרות ותצורה
# ==========================================
st.set_page_config(page_title="IBI Portfolio Tracker", layout="wide", page_icon="📊")

# עיצוב מותאם אישית (RTL לעברית)
st.markdown("""
<style>
    body {text-align: right; direction: rtl;}
    .stMetric {text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 22px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. נתונים קשיחים (Hardcoded Data)
# ==========================================

# חישוב מזומן מדויק לפי ה-PDF והדיווחים:
# התחלה (אחרי מכירות GLW/VIAV): +1,564.38
# קניית WDC (7 יח'): -1,900.71
# ביניים: -336.33
# --- החזרי מגן מס (מתוך ה-PDF) ---
# 28/02: +471.16
# 04/03: +270.83
# סה"כ תוספת מזומן ממס: +741.99
# יתרה סופית: 405.66 $
CASH_BALANCE_USD = 405.66

# רשימת החזרי מס שהתקבלו (לצורך חישוב רווח כולל אמיתי)
TAX_SHIELD_CREDITS = 741.99 

# תיק ההחזקות הנוכחי (פתוח)
CURRENT_PORTFOLIO = [
    {"Symbol": "GLW",  "Qty": 16, "Buy_Price": 145.54, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "SPOT", "Qty": 7,  "Buy_Price": 528.20, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "WDC",  "Qty": 7,  "Buy_Price": 270.53, "Date": "24.02.2026", "Fee": 7.0},
]

# היסטוריית עסקאות סגורות (לחישוב רווח/הפסד ממומש)
SOLD_HISTORY = [
    # --- עסקאות אחרונות (מתוך הדיווח שלך וה-PDF) ---
    {"Symbol": "TLN", "Qty": 11, "Sell_Price": 338.51, "Buy_Price": 359.89, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "AXTI", "Qty": 95, "Sell_Price": 39.75, "Buy_Price": 40.69, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "WDC", "Qty": 8, "Sell_Price": 270.00, "Buy_Price": 270.80, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "VIAV", "Qty": 98, "Sell_Price": 29.13, "Buy_Price": 26.34, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "GLW", "Qty": 22, "Sell_Price": 152.38, "Buy_Price": 131.90, "Date": "05.03.2026", "Fee_Total": 14.0},

    # --- עסקאות קודמות ---
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

# ==========================================
# 3. מנוע חישובים
# ==========================================
def get_data():
    # 1. שער דולר
    try:
        usd = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd = 3.60 # Fallback

    # 2. נתוני מניות חיות
    tickers_list = [p['Symbol'] for p in CURRENT_PORTFOLIO]
    if tickers_list:
        tickers = yf.Tickers(" ".join(tickers_list))
    
    live_data = []
    total_market_value = 0
    total_unrealized_pl = 0
    
    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        
        # משיכת מחיר
        try:
            t = tickers.tickers[sym]
            current_price = t.fast_info.last_price
            
            # ניסיון לקבל מחיר סגירה קודם אמין
            hist = t.history(period="5d")
            prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else t.fast_info.previous_close
        except:
            current_price = buy_price
            prev_close = buy_price

        # חישובים
        market_val = current_price * qty
        cost_basis = buy_price * qty
        unrealized_pl = market_val - cost_basis
        day_change_usd = current_price - prev_close
        day_change_pct = (day_change_usd / prev_close) * 100
        total_change_pct = (unrealized_pl / cost_basis) * 100

        total_market_value += market_val
        total_unrealized_pl += unrealized_pl

        # עיצוב צבעים
        def color(val, suffix=""):
            c = "green" if val >= 0 else "red"
            return f'<span style="color:{c}">{val:,.2f}{suffix}</span>'

        live_data.append({
            "Symbol": sym,
            "Qty": qty,
            "Price": f"${current_price:,.2f}",
            "Day Change": f"{color(day_change_usd, '$')} ({color(day_change_pct, '%')})",
            "Cost": f"${buy_price:,.2f}",
            "Value": f"${market_val:,.2f}",
            "Unrealized P/L": f"{color(unrealized_pl, '$')} ({color(total_change_pct, '%')})"
        })

    # 3. חישובים היסטוריים (Realized)
    total_realized_pl = 0
    total_fees = 0
    for trade in SOLD_HISTORY:
        # רווח/הפסד גולמי
        gross_pl = (trade['Sell_Price'] - trade['Buy_Price']) * trade['Qty']
        # עמלות
        fees = trade.get('Fee_Total', 14.0)
        # נטו לעסקה
        net_trade = gross_pl - fees
        
        total_realized_pl += net_trade
        total_fees += fees

    # עמלות על התיק הפתוח
    open_fees = sum([p['Fee'] for p in CURRENT_PORTFOLIO])
    
    return pd.DataFrame(live_data), usd, total_market_value, total_unrealized_pl, total_realized_pl, open_fees

# ==========================================
# 4. ממשק משתמש (UI)
# ==========================================
st.title("IBI Portfolio Dashboard 🇺🇸")

if st.button("🔄 רענן נתונים"):
    st.rerun()

with st.spinner("מושך נתונים מהבורסה..."):
    df, rate, port_val, unrealized, realized, open_fees = get_data()

# --- חישובים סופיים ---
# שווי תיק כולל (מזומן + מניות)
total_equity_usd = port_val + CASH_BALANCE_USD
total_equity_ils = total_equity_usd * rate

# רווח "אמיתי" (True Profit)
# הנוסחה: רווח מומש + רווח על הנייר - עמלות פתוחות + החזרי מס (מגן מס)
true_profit_usd = realized + unrealized - open_fees + TAX_SHIELD_CREDITS
true_profit_ils = true_profit_usd * rate

# אחוז תשואה כולל (ROI)
# ההון העצמי שהושקע = שווי נוכחי פחות הרווח שעשינו
invested_capital = total_equity_usd - true_profit_usd
roi_pct = (true_profit_usd / invested_capital * 100) if invested_capital > 0 else 0

# --- תצוגת מדדים (Metrics) ---
st.markdown("### 🏦 סטטוס חשבון (Status Snapshot)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("שווי תיק (USD)", f"${total_equity_usd:,.2f}")
col1.caption(f"שווי בשקלים: ₪{total_equity_ils:,.2f}")

col2.metric("מזומן נזיל", f"${CASH_BALANCE_USD:,.2f}", delta_color="normal")
col2.caption("כולל החזרי מגן מס")

col3.metric("רווח כולל אמיתי", f"${true_profit_usd:,.2f}", delta=f"{roi_pct:.2f}%")
col3.caption(f"כולל מגן מס: +${TAX_SHIELD_CREDITS:,.2f}")

col4.metric("שער דולר רציף", f"₪{rate:.3f}")

st.divider()

# --- לשוניות פירוט ---
tab1, tab2, tab3 = st.tabs(["📈 תיק מניות חי", "💰 ניתוח רווחים", "📜 יומן עסקאות"])

with tab1:
    if not df.empty:
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("התיק ריק כרגע.")

with tab2:
    st.subheader("פירוק הרווח וההפסד (P/L Breakdown)")
    c1, c2, c3 = st.columns(3)
    c1.metric("רווח מומש (סגור)", f"${realized:,.2f}", help="כולל עמלות מסחר")
    c2.metric("רווח על הנייר (פתוח)", f"${unrealized:,.2f}")
    c3.metric("זיכוי מגן מס (Cash In)", f"${TAX_SHIELD_CREDITS:,.2f}", help="כסף שנכנס לחשבון כהחזר מס")
    
    st.info(f"💡 **הסבר:** הסכום 'רווח כולל אמיתי' למעלה מחושב כך: רווח מומש ({realized:.0f}) + רווח פתוח ({unrealized:.0f}) + החזרי מס ({TAX_SHIELD_CREDITS}) - עמלות קנייה פתוחות ({open_fees}).")

with tab3:
    st.subheader("היסטוריית מכירות (סגורות)")
    
    hist_data = []
    for t in SOLD_HISTORY:
        net = (t['Sell_Price'] - t['Buy_Price']) * t['Qty'] - t.get('Fee_Total', 14)
        c = "green" if net > 0 else "red"
        hist_data.append({
            "Symbol": t['Symbol'],
            "Qty": t['Qty'],
            "Buy": f"${t['Buy_Price']}",
            "Sell": f"${t['Sell_Price']}",
            "Net Profit": f'<span style="color:{c}; font-weight:bold;">${net:,.2f}</span>',
            "Date": t['Date']
        })
    st.write(pd.DataFrame(hist_data).to_html(escape=False, index=False), unsafe_allow_html=True)

