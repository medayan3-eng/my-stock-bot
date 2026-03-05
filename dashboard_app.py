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
    .stMetric {text-align: center; border: 1px solid #eee; padding: 10px; border-radius: 5px;}
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #333;}
    div[data-testid="stMetricLabel"] {font-size: 16px; font-weight: normal;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. נתונים (Hardcoded Data)
# ==========================================

# חישוב יתרת מזומן מדויקת (Liquid Cash):
# --------------------------------------
# נקודת התחלה (אחרי מכירות GLW/VIAV): +1,564.38 $
# פחות קניית WDC (7 יח' + עמלה):      -1,900.71 $
# פחות קניית SPOT (7 יח' + עמלה):     -3,704.40 $ (528.2 * 7 + 7)
# פחות קניית GLW (16 יח' + עמלה):     -2,335.64 $ (145.54 * 16 + 7)
# פלוס מכירת TLN (נטו):               +3,709.61 $ (338.51 * 11 - 14)
# פלוס מכירת AXTI (נטו):              +3,762.25 $ (39.75 * 95 - 14)
# פלוס מכירת WDC (נטו, 8 יח'):        +2,146.00 $ (270.00 * 8 - 14)
# פלוס החזרי מגן מס (מה-PDF):         +741.99 $ (סכום מוערך של הזיכויים)
# --------------------------------------
# יתרה משוערת סופית: 3,983.48 $
# (הערה: היתרה עשויה להשתנות מעט בגלל תשלומי מס במקור שירדו, אך זהו המזומן הנזיל החיובי המוערך)
CASH_BALANCE_USD = 3983.48

# סך החזרי מס שנכנסו לחשבון (מגדילים את הרווח)
TAX_SHIELD_CREDITS = 741.99 

# תיק ההחזקות הנוכחי (Live Positions)
CURRENT_PORTFOLIO = [
    {"Symbol": "GLW",  "Qty": 16, "Buy_Price": 145.54, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "SPOT", "Qty": 7,  "Buy_Price": 528.20, "Date": "05.03.2026", "Fee": 7.0},
    {"Symbol": "WDC",  "Qty": 7,  "Buy_Price": 270.53, "Date": "24.02.2026", "Fee": 7.0},
]

# היסטוריית עסקאות סגורות (Realized P/L)
SOLD_HISTORY = [
    # עסקאות 05.03.2026
    {"Symbol": "TLN", "Qty": 11, "Sell_Price": 338.51, "Buy_Price": 359.89, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "AXTI", "Qty": 95, "Sell_Price": 39.75, "Buy_Price": 40.69, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "WDC", "Qty": 8, "Sell_Price": 270.00, "Buy_Price": 270.80, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "VIAV", "Qty": 98, "Sell_Price": 29.13, "Buy_Price": 26.34, "Date": "05.03.2026", "Fee_Total": 14.0},
    {"Symbol": "GLW", "Qty": 22, "Sell_Price": 152.38, "Buy_Price": 131.90, "Date": "05.03.2026", "Fee_Total": 14.0},

    # עסקאות עבר
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
        usd = 3.60

    # 2. נתוני מניות חיות
    tickers_list = [p['Symbol'] for p in CURRENT_PORTFOLIO]
    live_data = []
    total_market_value = 0
    total_unrealized_pl = 0
    
    if tickers_list:
        tickers = yf.Tickers(" ".join(tickers_list))
        for item in CURRENT_PORTFOLIO:
            sym = item['Symbol']
            qty = item['Qty']
            buy_price = item['Buy_Price']
            
            try:
                t = tickers.tickers[sym]
                current_price = t.fast_info.last_price
                hist = t.history(period="5d")
                prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else t.fast_info.previous_close
            except:
                current_price = buy_price
                prev_close = buy_price

            market_val = current_price * qty
            cost_basis = buy_price * qty
            unrealized_pl = market_val - cost_basis
            
            day_change_usd = current_price - prev_close
            day_change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            total_change_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

            total_market_value += market_val
            total_unrealized_pl += unrealized_pl

            def color(val, suffix=""):
                c = "#00c853" if val >= 0 else "#d50000"
                return f'<span style="color:{c}; font-weight:bold;">{val:,.2f}{suffix}</span>'

            live_data.append({
                "Symbol": sym,
                "Qty": qty,
                "Price": f"${current_price:,.2f}",
                "Change Today": f"{color(day_change_usd, '$')} ({color(day_change_pct, '%')})",
                "Avg Cost": f"${buy_price:,.2f}",
                "Value": f"${market_val:,.2f}",
                "Unrealized P/L": f"{color(unrealized_pl, '$')} ({color(total_change_pct, '%')})"
            })

    # 3. חישובים היסטוריים
    total_realized_pl = 0
    total_commissions = 0
    
    for trade in SOLD_HISTORY:
        gross_pl = (trade['Sell_Price'] - trade['Buy_Price']) * trade['Qty']
        fees = trade.get('Fee_Total', 14.0)
        net_trade = gross_pl - fees
        
        total_realized_pl += net_trade
        total_commissions += fees

    open_fees = sum([p['Fee'] for p in CURRENT_PORTFOLIO])
    total_commissions += open_fees
    
    return pd.DataFrame(live_data), usd, total_market_value, total_unrealized_pl, total_realized_pl, total_commissions

# ==========================================
# 4. ממשק משתמש (UI)
# ==========================================
st.title("IBI Portfolio Tracker 🇺🇸")
st.caption("מעקב מלא אחר תיק ההשקעות, כולל עמלות, מגן מס וסטטוס אמת.")

if st.button("🔄 רענן נתונים עכשיו"):
    st.rerun()

with st.spinner("מבצע חישובים..."):
    df, rate, port_val, unrealized, realized, total_fees = get_data()

# --- חישובים סופיים ---
# שווי תיק כולל (Total Equity)
total_equity_usd = port_val + CASH_BALANCE_USD
total_equity_ils = total_equity_usd * rate

# רווח "אמיתי" (True Profit)
# נוסחה: (רווח מומש + רווח פתוח) + החזרי מס - עמלות שטרם קוזזו
# הערה: עמלות המימוש כבר קוזזו ב-realized, אז מורידים רק עמלות פתוחות אם לא קוזזו, אבל בנוסחה שלי realized הוא כבר נטו.
# אז: realized (Net) + unrealized (Gross) - open_fees + Tax_Shield
open_fees = sum([p['Fee'] for p in CURRENT_PORTFOLIO])
true_profit_usd = realized + unrealized - open_fees + TAX_SHIELD_CREDITS
true_profit_ils = true_profit_usd * rate

# תשואה (ROI)
invested_capital = total_equity_usd - true_profit_usd
roi_pct = (true_profit_usd / invested_capital * 100) if invested_capital > 0 else 0

# --- תצוגת מדדים ---
st.markdown("### 🏦 סטטוס חשבון (Account Snapshot)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("שווי תיק כולל ($)", f"${total_equity_usd:,.2f}")
c1.caption(f"שווי בשקלים: ₪{total_equity_ils:,.2f}")

c2.metric("מזומן נזיל ($)", f"${CASH_BALANCE_USD:,.2f}")
c2.caption("כולל החזרי מס ודיבידנדים")

c3.metric("רווח כולל אמיתי", f"${true_profit_usd:,.2f}", delta=f"{roi_pct:.2f}%")
c3.caption(f"כולל מגן מס בסך ${TAX_SHIELD_CREDITS}")

c4.metric("שער דולר רציף", f"₪{rate:.3f}")

st.divider()

# --- לשוניות ---
tab1, tab2, tab3 = st.tabs(["📈 תיק מניות חי", "💰 פירוט רווח והפסד", "📜 היסטוריית פעולות"])

with tab1:
    if not df.empty:
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("אין פוזיציות פתוחות כרגע.")

with tab2:
    st.subheader("ניתוח רווחים (P/L Breakdown)")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("רווח מומש (נטו)", f"${realized:,.2f}", help="רווח מעסקאות סגורות בניכוי עמלות")
    col2.metric("רווח על הנייר (ברוטו)", f"${unrealized:,.2f}", help="רווח מעסקאות פתוחות לפני עמלת מכירה")
    col3.metric("סה״כ עמלות ששולמו", f"${total_fees:,.2f}", help="כל העמלות ששולמו ל-IBI עד היום")
    col4.metric("זיכוי מגן מס (החזר)", f"+${TAX_SHIELD_CREDITS:,.2f}", help="כסף שנכנס לחשבון כהחזר מס")

with tab3:
    st.subheader("יומן עסקאות סגורות")
    hist_data = []
    for t in SOLD_HISTORY:
        net = (t['Sell_Price'] - t['Buy_Price']) * t['Qty'] - t.get('Fee_Total', 14)
        c = "green" if net > 0 else "red"
        hist_data.append({
            "Symbol": t['Symbol'],
            "Qty": t['Qty'],
            "Buy Price": f"${t['Buy_Price']}",
            "Sell Price": f"${t['Sell_Price']}",
            "Net Profit": f'<span style="color:{c}; font-weight:bold;">${net:,.2f}</span>',
            "Date": t['Date']
        })
    st.write(pd.DataFrame(hist_data).to_html(escape=False, index=False), unsafe_allow_html=True)
