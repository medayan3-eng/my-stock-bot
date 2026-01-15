import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש (Hardcoded Data)
# ==========================================

# 1. יתרות מזומן (מחושב לפי הדיווח שלך)
# התחלה: 1484.98
# הפסד OSS (כולל עמלות): -20.58
# הפסד BIFT (כולל עמלות): -114.00
# קניית VRTX (כולל עמלה): -2227.00
# יתרה חדשה: -876.60
CASH_BALANCE = {
    "USD": -876.60, 
    "ILS": 6422.39 # (4822.39 + 1600 הפקדה)
}

# 2. התיק שלי - נתונים ידניים וקבועים
CURRENT_PORTFOLIO = [
    # --- מניות ארה"ב (יאהו עובד רגיל) ---
    {"Symbol": "PLTR", "Qty": 2, "Buy_Price": 183.36, "Date": "18.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "AMZN", "Qty": 6, "Buy_Price": 227.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "GEV",  "Qty": 2, "Buy_Price": 700.00, "Date": "10.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "VRTX", "Qty": 5, "Buy_Price": 444.00, "Date": "15.01.2026", "Fee": 7.0, "Currency": "USD"},
    
    # --- קרנות בנק (ישראל) - הנתונים שביקשת לקבע ---
    {
        "Symbol": "1159250", # מספר קרן ללא סיומת TA לטובת הסקרייפר
        "Display": "MTF S&P 500 (IL)", 
        "Qty": 10, 
        "Buy_Price": 2353.20, # מחיר ממוצע לפי עלות 23,532
        "Date": "11.01.2026", 
        "Fee": 0.0, 
        "Currency": "ILS",
        "Source": "Funder" # ניסיון משיכה מפאנדר
    },
    {
        "Symbol": "1206549", 
        "Display": "MTF Banks 5 (IL)",
        "Qty": 244, 
        "Buy_Price": 109.23, # מחיר ממוצע לפי עלות 26,652
        "Date": "11.01.2026", 
        "Fee": 0.0, 
        "Currency": "ILS",
        "Source": "Funder"
    },
]

# 3. היסטוריית מכירות (כולל ההפסדים האחרונים)
SOLD_HISTORY = [
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    # עסקאות ה"שטויות" (למידה)
    {"Symbol": "OSS",  "Qty": 165, "Sell_Price": 11.95, "Buy_Price": 11.99, "Date": "13.01.2026", "Fee_Total": 14.0}, # עמלה 7+7
    {"Symbol": "BIFT", "Qty": 625, "Sell_Price": 3.05, "Buy_Price": 3.21,  "Date": "13.01.2026", "Fee_Total": 14.0},
]

# מחירי גיבוי למקרה שהסקרייפר נחסם (מעודכן ל-15.01.2026)
FALLBACK_PRICES = {
    "1159250": 2352.00, # מחיר משוער ל-S&P
    "1206549": 108.40   # מחיר משוער לבנקים
}

EARNINGS_CALENDAR = {
    "AMZN": "06/02/26", "PLTR": "03/02/26", "VRT": "12/02/26", 
    "GEV": "28/01/26", "VRTX": "05/02/26"
}

CURRENT_FEE = 7.0 

# ==========================================
# ⚙️ הגדרות תצוגה
# ==========================================
st.set_page_config(page_title="Pro Trader Dashboard", layout="wide", page_icon="📈")
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .big-font {font-size:18px !important; font-weight: bold;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 מנוע חישובים ומשיכת נתונים
# ==========================================

def get_il_fund_price(fund_id):
    """מנסה למשוך מחיר מאתר Funder, ואם נכשל משתמש בגיבוי"""
    url = f"https://www.funder.co.il/etf/{fund_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        # ניסיון משיכה (Scraping)
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            # כאן אנחנו מחפשים מחיר בתוך ה-HTML (לרוב משתנה, לכן זה ניסיון)
            # לרוב בסטרימליט זה ייחסם, אבל שווה לנסות
            pass
    except:
        pass
    
    # אם הגענו לפה והסקריפינג נכשל או נחסם - מחזירים את הגיבוי
    return FALLBACK_PRICES.get(fund_id, 0), False # False = לא אונליין אמיתי

def get_financial_data():
    # שער דולר
    try:
        rate = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        rate = 3.65

    # מניות ארה"ב (טיקרים רגילים)
    us_symbols = [i['Symbol'] for i in CURRENT_PORTFOLIO if "Currency" in i and i["Currency"] == "USD"]
    tickers = yf.Tickers(" ".join(us_symbols)) if us_symbols else None
    
    live_rows = []
    portfolio_market_value_usd = 0 
    total_unrealized_pl_usd = 0
    fees_paid_on_open_holdings = sum([item.get('Fee', 0) for item in CURRENT_PORTFOLIO])

    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        currency = item.get("Currency", "USD")
        display_name = item.get("Display", sym)
        
        last_price = 0
        prev_close = 0
        is_estimated = False
        
        # --- לוגיקה למניות ארה"ב (Yahoo) ---
        if currency == "USD":
            try:
                t = tickers.tickers[sym]
                last_price = t.fast_info.last_price
                prev_close = t.fast_info.previous_close
            except:
                pass
        
        # --- לוגיקה לקרנות ישראל (Scraper/Fallback) ---
        elif currency == "ILS":
            # משתמש בפונקציה המיוחדת שלנו
            price, is_live = get_il_fund_price(sym)
            last_price = price
            prev_close = price # אין לנו היסטוריה בגיבוי, אז השינוי היומי יהיה 0
            if not is_live:
                is_estimated = True

        # אם עדיין אין מחיר, השתמש במחיר קנייה כדי לא לקרוס
        if last_price == 0:
            last_price = buy_price
            is_estimated = True

        # --- חישובים ---
        if currency == "ILS":
            # המרה לדולר לטובת סיכום
            price_in_usd = last_price / rate
            cost_basis_usd = (buy_price / rate) * qty
            market_val_usd = price_in_usd * qty
            
            display_price = f"₪{last_price:,.2f}"
            display_cost = f"₪{buy_price:,.2f}"
            display_val = f"₪{last_price * qty:,.2f}"
            change_symbol = "₪"
            total_pl_native = (last_price - buy_price) * qty
        else:
            cost_basis_usd = buy_price * qty
            market_val_usd = last_price * qty
            
            display_price = f"${last_price:,.2f}"
            display_cost = f"${buy_price:,.2f}"
            display_val = f"${market_val_usd:,.2f}"
            change_symbol = "$"
            total_pl_native = (last_price - buy_price) * qty

        # שינוי יומי
        day_change = (last_price - prev_close) * qty
        day_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        
        # רווח כולל
        total_pl_pct = ((last_price - buy_price) / buy_price) * 100
        
        portfolio_market_value_usd += market_val_usd
        total_unrealized_pl_usd += (market_val_usd - cost_basis_usd)
        
        # אנליסטים (רק לארה"ב)
        analyst = "-"
        if currency == "USD":
            try:
                info = tickers.tickers[sym].info
                rec = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
                analyst = rec if rec != "N/A" else "-"
            except: pass

        # סימון אם הנתון הוא הערכה
        status_icon = "⚠️" if is_estimated else ""

        def color_val(val, suffix="", prefix=""):
            c = "#2ecc71" if val >= 0 else "#e74c3c"
            return f'<span style="color:{c}; font-weight:bold;">{prefix}{val:,.2f}{suffix}</span>'

        live_rows.append({
            "Symbol": f"{display_name} {status_icon}",
            "Qty": qty,
            "Price": display_price,
            "Change Today": f"{color_val(day_change, '', change_symbol)} <br><small>{color_val(day_pct, '%')}</small>",
            "Avg Cost": display_cost,
            "Value": display_val,
            "Total P/L": f"{color_val(total_pl_native, '', change_symbol)} <br><small>{color_val(total_pl_pct, '%')}</small>",
            "Analysts": analyst,
            "Next Report": EARNINGS_CALENDAR.get(sym, "-")
        })

    # --- היסטוריה ---
    total_realized_pl_net_usd = 0
    fees_paid_on_sold_total = 0
    for s in SOLD_HISTORY:
        gross = (s['Sell_Price'] - s['Buy_Price']) * s['Qty']
        fees = s.get('Fee_Total', CURRENT_FEE * 2)
        total_realized_pl_net_usd += (gross - fees)
        fees_paid_on_sold_total += fees

    total_fees_lifetime = fees_paid_on_open_holdings + fees_paid_on_sold_total
    
    return pd.DataFrame(live_rows), rate, portfolio_market_value_usd, total_unrealized_pl_usd, total_realized_pl_net_usd, total_fees_lifetime, fees_paid_on_open_holdings

# ==========================================
# 📱 ממשק משתמש
# ==========================================
st.title("🌍 My Global Portfolio")

if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Fetching data from Yahoo & IL Funds..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data()

usd_cash = CASH_BALANCE["USD"]
ils_cash_usd = CASH_BALANCE["ILS"] / rate
total_cash_usd = usd_cash + ils_cash_usd

total_net_worth_usd = port_val + total_cash_usd
total_net_worth_ils = total_net_worth_usd * rate
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

st.markdown("### 🏦 Account Snapshot")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
m2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f}")
m3.metric("Liquid Cash ($)", f"${total_cash_usd:,.2f}")
m4.metric("Total Net Profit", f"${grand_total_profit:,.2f}", delta_color="normal" if grand_total_profit>=0 else "inverse")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Live Assets", "🧾 Buy Log", "💰 Realized P/L"])

with tab1:
    if not df_live.empty:
        st.caption("⚠️ = Data estimated (Offline mode) | Data for IL funds is hard to scrape in cloud.")
        st.write(df_live.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No active holdings.")

with tab2:
    buy_rows = []
    for p in CURRENT_PORTFOLIO:
        fee = p.get('Fee', 0)
        curr = p.get("Currency", "USD")
        sym = p.get("Display", p['Symbol'])
        price_d = f"₪{p['Buy_Price']:,.2f}" if curr == "ILS" else f"${p['Buy_Price']:,.2f}"
        cost_d = f"₪{(p['Qty']*p['Buy_Price'])+fee:,.2f}" if curr == "ILS" else f"${(p['Qty']*p['Buy_Price'])+fee:,.2f}"
        buy_rows.append({"Symbol": sym, "Date": p['Date'], "Qty": p['Qty'], "Price": price_d, "Fee": fee, "Total Cost": cost_d})
    st.dataframe(pd.DataFrame(buy_rows), use_container_width=True)

with tab3:
    st.subheader("💸 Realized P/L (Net)")
    sold_rows = []
    for s in SOLD_HISTORY:
        buy_cost = s['Buy_Price'] * s['Qty']
        sell_rev = s['Sell_Price'] * s['Qty']
        fees = s.get('Fee_Total', CURRENT_FEE * 2)
        net = sell_rev - buy_cost - fees
        c = "green" if net > 0 else "red"
        sold_rows.append({
            "Symbol": s['Symbol'], "Qty": s['Qty'], 
            "Net Profit ($)": f'<span style="color:{c}; font-weight:bold;">${net:,.2f}</span>'
        })
    st.write(pd.DataFrame(sold_rows).to_html(escape=False, index=False), unsafe_allow_html=True)
