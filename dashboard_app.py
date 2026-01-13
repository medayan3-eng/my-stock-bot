import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import time

# ==========================================
# 💾 מאגר הנתונים המרכזי (Data Store)
# ==========================================
# כאן אתה מזין את הנתונים שלך ידנית. המערכת תחשב לבד את כל השאר.

# 1. יתרות מזומן עדכניות (כפי שביקשת)
CASH_BALANCE = {
    "USD": 1484.98,
    "ILS": 3222.39
}

# 2. המניות שאתה מחזיק כרגע (Holdings)
CURRENT_PORTFOLIO = [
    {"Symbol": "PLTR", "Qty": 2, "Buy_Price": 183.36, "Date": "18.12.2025"},
    {"Symbol": "AMZN", "Qty": 6, "Buy_Price": 227.00, "Date": "22.12.2025"},
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025"},
    {"Symbol": "GEV",  "Qty": 2, "Buy_Price": 700.00, "Date": "10.12.2025"},
]

# 3. היסטוריית מכירות (Sold) - לחישוב רווח ממומש
# הערה: הזנתי את נתוני הקנייה המקוריים לפי התמונות הקודמות שלך כדי לחשב רווח אמיתי
SOLD_HISTORY = [
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026"},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026"}
]

# עמלה קבועה לכל פעולה (קנייה או מכירה)
COMMISSION_FEE = 7.0 

# ==========================================
# ⚙️ הגדרות מערכת ותצוגה
# ==========================================
st.set_page_config(page_title="Pro Trader Dashboard", layout="wide", page_icon="📈")
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .big-font {font-size:24px !important; font-weight: bold;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 מנוע חישוב ואיסוף נתונים
# ==========================================
def get_live_data():
    """מושך נתונים בזמן אמת לכל המניות בתיק + שער דולר"""
    
    # 1. משיכת שער דולר-שקל
    try:
        usd_ils = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_ils = 3.65 # גיבוי
        
    # 2. הכנת רשימת מניות למשיכה
    symbols = [item['Symbol'] for item in CURRENT_PORTFOLIO]
    if not symbols:
        return pd.DataFrame(), usd_ils

    # 3. משיכת נתונים מרוכזת (Batch Fetch)
    tickers = yf.Tickers(" ".join(symbols))
    
    live_data = []
    total_market_value = 0
    total_unrealized_pl = 0
    
    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        
        try:
            # שליפת מידע מ-Yahoo
            info = tickers.tickers[sym].info
            fast_info = tickers.tickers[sym].fast_info
            
            # נתונים בזמן אמת
            last_price = fast_info.last_price
            prev_close = fast_info.previous_close
            
            # ניסיון להשיג נתונים עמוקים (Bid/Ask/Range)
            bid = info.get('bid', 0)
            ask = info.get('ask', 0)
            day_high = info.get('dayHigh', 0)
            day_low = info.get('dayLow', 0)
            
            # תאריך דוחות (Earnings)
            try:
                # מנסה למצוא את התאריך הבא
                calendar = tickers.tickers[sym].calendar
                if calendar is not None and not calendar.empty:
                    # בדיקה איפה התאריך נמצא (משתנה בין גרסאות)
                    earnings_date = calendar.iloc[0, 0] if isinstance(calendar.iloc[0, 0], (datetime, pd.Timestamp)) else "TBD"
                    if isinstance(earnings_date, (datetime, pd.Timestamp)):
                        earnings_date = earnings_date.strftime("%d/%m/%y")
                else:
                    earnings_date = "-"
            except:
                earnings_date = "-"

            # --- חישובים ---
            market_val = last_price * qty
            cost_basis = buy_price * qty
            
            # שינוי יומי ($)
            day_change_dollar = last_price - prev_close
            
            # רווח/הפסד יומי ($)
            day_pl = day_change_dollar * qty
            
            # רווח/הפסד כולל ($)
            total_pl = market_val - cost_basis
            total_pl_pct = (total_pl / cost_basis) * 100
            
            total_market_value += market_val
            total_unrealized_pl += total_pl

            # עיצוב HTML לרווח והפסד (צבעים בתוך הטבלה)
            color = "green" if total_pl >= 0 else "red"
            sign = "+" if total_pl >= 0 else ""
            pl_display = f'<span style="color:{color}; font-weight:bold;">{sign}{total_pl:,.2f}$<br><span style="font-size:0.8em;">({sign}{total_pl_pct:.2f}%)</span></span>'
            
            day_pl_color = "green" if day_pl >= 0 else "red"
            day_pl_display = f'<span style="color:{day_pl_color}">{day_pl:,.2f}$</span>'

            live_data.append({
                "Symbol": sym,
                "Qty": qty,
                "Last Price": f"${last_price:.2f}",
                "Change ($)": f"{day_change_dollar:+.2f}",
                "Bid / Ask": f"{bid:.2f} / {ask:.2f}",
                "Day Range": f"{day_low:.2f}-{day_high:.2f}",
                "Cost": f"${buy_price:.2f}",
                "Market Value": f"${market_val:,.2f}",
                "Daily P/L": day_pl_display,
                "Total P/L": pl_display, # עמודה מיוחדת עם HTML
                "Reports": earnings_date,
                # נתונים גולמיים למיון אם נצטרך
                "_raw_pl": total_pl
            })
            
        except Exception as e:
            # במקרה של תקלה במניה ספציפית
            live_data.append({"Symbol": sym, "Qty": qty, "Last Price": "Error"})
            print(f"Error {sym}: {e}")

    return pd.DataFrame(live_data), usd_ils, total_market_value, total_unrealized_pl

# ==========================================
# 📱 ממשק האפליקציה (UI)
# ==========================================

st.title("🏛️ My Investment Command Center")

# כפתור רענון
if st.button("🔄 REFRESH MARKET DATA", type="primary", use_container_width=True):
    st.rerun()

# --- טעינת נתונים ---
with st.spinner("Connecting to Wall St..."):
    df_live, rate, portfolio_val, total_pl_val = get_live_data()

# --- חישובי תיק כוללים ---
usd_cash = CASH_BALANCE["USD"]
ils_cash = CASH_BALANCE["ILS"]
ils_cash_in_usd = ils_cash / rate

# שווי חשבון כולל (מניות + מזומן דולרי + מזומן שקלי מומר)
total_net_worth_usd = portfolio_val + usd_cash + ils_cash_in_usd
total_net_worth_ils = total_net_worth_usd * rate

# כוח קנייה (מזומן דולרי + המרה של השקלים לדולר)
buying_power = usd_cash + ils_cash_in_usd

# --- כרטיסי מידע (Metrics) ---
st.markdown("### 🏦 Account Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Net Worth ($)", f"${total_net_worth_usd:,.2f}")
with col2:
    st.metric("Total Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f} ₪/$")
with col3:
    st.metric("Portfolio Value (Stocks)", f"${portfolio_val:,.2f}")
with col4:
    st.metric("Buying Power", f"${buying_power:,.2f}", "Liquid Cash")

st.markdown("---")

# כרטיס רווח/הפסד מיוחד
pl_color = "normal" if total_pl_val == 0 else "inverse" # טריק לצבע
st.metric("Total Unrealized P/L (Open Positions)", f"${total_pl_val:,.2f}", delta_color=pl_color)

st.markdown("---")

# --- לשוניות (Tabs) ---
tab1, tab2, tab3 = st.tabs(["📊 Live Assets", "🛒 Buy History", "💰 Sell History"])

# 1️⃣ לשונית תיק חי (Live Assets)
with tab1:
    st.subheader("Current Holdings")
    if not df_live.empty:
        # שימוש ב-HTML כדי להציג את הצבעים בטבלה
        st.write(df_live.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No holdings currently.")

# 2️⃣ לשונית היסטוריית קניות (Buy History)
with tab2:
    st.subheader("🧾 Purchase Log")
    buy_data = []
    total_buy_commissions = 0
    
    # חישוב היסטוריית קניות של התיק הנוכחי
    for item in CURRENT_PORTFOLIO:
        val = item['Qty'] * item['Buy_Price']
        commission = COMMISSION_FEE
        total_buy_commissions += commission
        buy_data.append({
            "Symbol": item['Symbol'],
            "Date": item['Date'],
            "Qty": item['Qty'],
            "Price": f"${item['Buy_Price']:.2f}",
            "Total Cost": f"${val:,.2f}",
            "Commission": f"${commission:.2f}"
        })
    
    # הוספת קניות של מניות שנמכרו (כדי שההיסטוריה תהיה מלאה)
    for item in SOLD_HISTORY:
        val = item['Qty'] * item['Buy_Price']
        commission = COMMISSION_FEE
        total_buy_commissions += commission
        buy_data.append({
            "Symbol": item['Symbol'] + " (Sold)",
            "Date": "History", # או להוסיף תאריך אם ידוע
            "Qty": item['Qty'],
            "Price": f"${item['Buy_Price']:.2f}",
            "Total Cost": f"${val:,.2f}",
            "Commission": f"${commission:.2f}"
        })

    df_buy = pd.DataFrame(buy_data)
    st.table(df_buy)
    st.caption(f"Total Buy Commissions Paid: ${total_buy_commissions:.2f}")

# 3️⃣ לשונית היסטוריית מכירות (Sell History)
with tab3:
    st.subheader("💸 Realized Gains/Losses")
    sell_data = []
    total_realized_pl = 0
    total_sell_commissions = 0
    
    for item in SOLD_HISTORY:
        qty = item['Qty']
        sell_price = item['Sell_Price']
        buy_price = item['Buy_Price']
        
        # חישובים
        sale_proceeds = qty * sell_price
        cost_basis = qty * buy_price
        commission = COMMISSION_FEE
        
        # רווח נקי = (מכירה - קנייה) פחות עמלת מכירה
        # הערה: יש גם עמלת קנייה, מחמירים יכולים להוריד גם אותה (כאן הורדנו רק עמלת פעולה נוכחית)
        realized_pl = (sale_proceeds - cost_basis) - commission
        
        total_realized_pl += realized_pl
        total_sell_commissions += commission
        
        # צבע לרווח/הפסד
        color = "green" if realized_pl > 0 else "red"
        
        sell_data.append({
            "Symbol": item['Symbol'],
            "Date Sold": item['Date'],
            "Qty": qty,
            "Sell Price": f"${sell_price:.2f}",
            "Buy Price": f"${buy_price:.2f}",
            "Proceeds": f"${sale_proceeds:,.2f}",
            "Commission": f"${commission:.2f}",
            "Realized P/L": f'<span style="color:{color}; font-weight:bold;">${realized_pl:,.2f}</span>'
        })
        
    if sell_data:
        df_sell = pd.DataFrame(sell_data)
        st.write(df_sell.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        st.markdown("---")
        col_s1, col_s2 = st.columns(2)
        col_s1.metric("Total Realized Profit", f"${total_realized_pl:,.2f}")
        col_s2.metric("Total Sell Commissions", f"${total_sell_commissions:.2f}")
    else:
        st.info("No sales executed yet.")

# --- תחתית הדף ---
st.markdown("---")
st.caption(f"System updated: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Data provided by Yahoo Finance | Fees: $7 flat rate")
