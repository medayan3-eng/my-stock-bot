import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש
# ==========================================

# 1. יתרות מזומן
# חישוב:
# התחלה: -314.72
# מכירת AMTM (נטו): +2,822.60
# קניית PESI (כולל עמלה): -3,239.94
# יתרה חדשה: -732.06
CASH_BALANCE = {
    "USD": -732.06, 
    "ILS": -50732.55 
}

# 2. התיק הנוכחי
CURRENT_PORTFOLIO = [
    # --- מניות ארה"ב (IBI) ---
    {"Symbol": "SMH",  "Qty": 11, "Buy_Price": 404.40, "Date": "03.02.2026", "Fee": 7.0, "Currency": "USD"},
    {"Symbol": "PESI", "Qty": 218, "Buy_Price": 14.83, "Date": "12.02.2026", "Fee": 7.0, "Currency": "USD"},

    # --- מניות ישראל (בנק) ---
    {
        "Symbol": "YELN-F5.TA", 
        "Name": "Yelin Lapidot Banks",
        "Qty": 244, 
        "Buy_Price": 10923.21, # אגורות
        "Date": "09.01.2026", 
        "Fee_ILS": 75.0, 
        "Currency": "ILS"
    },
    {
        "Symbol": "KSM-F72.TA", 
        "Name": "KSM ETF TA-90",
        "Qty": 68,       
        "Buy_Price": 36366.18, # אגורות
        "Date": "19.01.2026", 
        "Fee_ILS": 75.0, 
        "Currency": "ILS"
    },
]

# 3. היסטוריית מכירות
SOLD_HISTORY = [
    # --- מכירות חדשות (12.02.2026) ---
    # AMTM: קנייה 32.40 | מכירה 31.44 | כמות 90 | עמלה 14 (7+7)
    {"Symbol": "AMTM", "Qty": 90, "Sell_Price": 31.44, "Buy_Price": 32.40, "Date": "12.02.2026", "Fee_Total": 14.0},

    # --- מכירות קודמות ---
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
    "SMH": "N/A", "PESI": "TBD"
}

CURRENT_FEE = 7.0 

# ==========================================
# ⚙️ הגדרות תצוגה
# ==========================================
st.set_page_config(page_title="Global Portfolio", layout="wide", page_icon="🌍")
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .big-font {font-size:18px !important; font-weight: bold;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 מנוע חישובים פיננסיים
# ==========================================
def get_financial_data(manual_prices):
    try:
        usd_ils_ticker = yf.Ticker("ILS=X").history(period="1d")
        if not usd_ils_ticker.empty:
            rate = usd_ils_ticker['Close'].iloc[-1]
        else:
            rate = 3.65
    except:
        rate = 3.65

    symbols = [i['Symbol'] for i in CURRENT_PORTFOLIO]
    if not symbols: 
        total_realized_pl_net_usd = 0
        fees_paid_on_sold_total = 0
        for s in SOLD_HISTORY:
            gross = (s['Sell_Price'] - s['Buy_Price']) * s['Qty']
            fees = s.get('Fee_Total', CURRENT_FEE * 2)
            total_realized_pl_net_usd += (gross - fees)
            fees_paid_on_sold_total += fees
        return pd.DataFrame(), rate, 0, 0, total_realized_pl_net_usd, fees_paid_on_sold_total, 0

    tickers = yf.Tickers(" ".join(symbols))
    
    live_rows = []
    portfolio_market_value_usd = 0 
    total_unrealized_pl_usd = 0
    fees_paid_on_open_holdings = sum([item.get('Fee', 0) for item in CURRENT_PORTFOLIO])

    # הוספת עמלות שקליות לחישוב הכללי
    fees_ils_total = sum([item.get('Fee_ILS', 0) for item in CURRENT_PORTFOLIO])
    fees_paid_on_open_holdings += (fees_ils_total / rate)

    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        currency = item.get("Currency", "USD")
        display_name = item.get("Name", sym.replace(".TA", " (IL)"))
        
        last_price = 0
        prev_close = 0
        
        # 1. מחיר ידני
        manual_val = manual_prices.get(sym, 0)
        if manual_val > 0:
            last_price = manual_val
            # המרה מאגורות אם צריך
            if sym.endswith(".TA") and last_price > 500: 
                last_price = last_price / 100
            prev_close = last_price 
        else:
            # 2. משיכה מיאהו
            try:
                t = tickers.tickers[sym]
                last_price = t.fast_info.last_price
                prev_close = t.fast_info.previous_close
                
                # תיקון אגורות לישראל
                if sym.endswith(".TA"):
                    last_price = last_price / 100
                    prev_close = prev_close / 100
            except:
                pass

        if not last_price or last_price == 0:
            last_price = buy_price # Fallback
            prev_close = buy_price

        # --- חישובים ---
        if currency == "ILS":
            # נתונים מת"א מגיעים באגורות (לרוב)
            price_ils = last_price / 100
            buy_price_ils = buy_price / 100
            
            # המרה לדולר לטובת הטוטאל
            market_val_usd = (price_ils * qty) / rate
            cost_basis_usd = (buy_price_ils * qty) / rate
            
            # מחרוזות לתצוגה
            display_price = f"₪{price_ils:,.2f}"
            display_cost = f"₪{buy_price_ils:,.2f}"
            display_val = f"₪{price_ils * qty:,.2f}"
            change_symbol = "₪"
            
            # רווח/הפסד בשקלים
            total_pl_native = (price_ils - buy_price_ils) * qty
            day_change = (price_ils - (prev_close/100)) * qty
            
            # חישוב אחוזים
            total_pl_pct = ((price_ils - buy_price_ils) / buy_price_ils) * 100
            day_pct = ((price_ils - (prev_close/100)) / (prev_close/100)) * 100 if prev_close > 0 else 0

        else: # USD
            cost_basis_usd = buy_price * qty
            market_val_usd = last_price * qty
            
            display_price = f"${last_price:,.2f}"
            display_cost = f"${buy_price:,.2f}"
            display_val = f"${market_val_usd:,.2f}"
            change_symbol = "$"
            
            total_pl_native = (last_price - buy_price) * qty
            day_change = (last_price - prev_close) * qty
            
            total_pl_pct = ((last_price - buy_price) / buy_price) * 100
            day_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

        
        portfolio_market_value_usd += market_val_usd
        total_unrealized_pl_usd += (market_val_usd - cost_basis_usd)
        
        analyst = "-"
        if currency == "USD":
            try:
                info = tickers.tickers[sym].info
                rec = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
                analyst = rec if rec != "N/A" else "-"
            except: pass

        def color_val(val, suffix="", prefix=""):
            c = "#2ecc71" if val >= 0 else "#e74c3c"
            return f'<span style="color:{c}; font-weight:bold;">{prefix}{val:,.2f}{suffix}</span>'

        live_rows.append({
            "Symbol": display_name,
            "Qty": qty,
            "Price": display_price,
            "Change Today": f"{color_val(day_change, '', change_symbol)} <br><small>{color_val(day_pct, '%')}</small>",
            "Avg Cost": display_cost,
            "Value": display_val,
            "Total P/L": f"{color_val(total_pl_native, '', change_symbol)} <br><small>{color_val(total_pl_pct, '%')}</small>",
            "Analysts": analyst,
            "Next Report": EARNINGS_CALENDAR.get(sym, "-")
        })

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
# 📱 ממשק
# ==========================================
st.title("🌍 My Global Portfolio")

# סרגל צד לתיקון ידני
st.sidebar.header("🛠️ Manual Price Fix")
manual_prices = {}
for p in CURRENT_PORTFOLIO:
    if p.get("Currency") == "ILS":
        sym = p['Symbol']
        name = p.get("Name", sym)
        val = st.sidebar.number_input(f"{name} (Agorot)", min_value=0.0, value=0.0, step=0.1)
        manual_prices[sym] = val

if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Fetching Global Data..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data(manual_prices)

# חישוב שווי נקי כולל
total_net_worth_usd = port_val + CASH_BALANCE["USD"]
total_net_worth_ils = total_net_worth_usd * rate
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

st.markdown("### 🏦 Account Snapshot")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
m2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f}")
m3.metric("Liquid Cash ($)", f"${CASH_BALANCE['USD']:,.2f}") 
m4.metric("Total Net Profit", f"${grand_total_profit:,.2f}", delta_color="normal" if grand_total_profit>=0 else "inverse")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Live Assets", "🧾 Buy Log", "💰 Realized P/L"])

with tab1:
    if not df_live.empty:
        st.write(df_live.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No active holdings.")

with tab2:
    buy_rows = []
    for p in CURRENT_PORTFOLIO:
        fee = p.get('Fee', 0)
        curr = p.get("Currency", "USD")
        sym = p.get("Name", p['Symbol'].replace(".TA", " (IL)"))
        
        if curr == "ILS":
            fee = p.get('Fee_ILS', 0)
            price_d = f"₪{p['Buy_Price']/100:,.2f}" # הצגה בשקלים
            cost_d = f"₪{((p['Qty']*p['Buy_Price'])/100)+fee:,.2f}"
        else:
            price_d = f"${p['Buy_Price']:,.2f}"
            cost_d = f"${(p['Qty']*p['Buy_Price'])+fee:,.2f}"
            
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
