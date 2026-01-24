import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש (Hardcoded Data)
# ==========================================

# 1. יתרות מזומן (עודכן לאחר מכירת GEV)
# היינו במינוס 21.02$, נכנסו 1301.42$ נטו
CASH_BALANCE = {
    "USD": 1280.40, 
    "ILS": 798.45 
}

# 2. התיק הנוכחי (החזקות פתוחות בלבד)
CURRENT_PORTFOLIO = [
    # החזקה חדשה
    {"Symbol": "ALB",  "Qty": 26, "Buy_Price": 172.00, "Date": "20.01.2026", "Fee": 7.0},
    
    # החזקות ותיקות
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025", "Fee": 7.5},
]

# 3. היסטוריית מכירות (עסקאות סגורות)
SOLD_HISTORY = [
    # מכירה אחרונה (24.01.2026)
    # GEV: קנייה 700 (עמלה 7.5) | מכירה 654.21 (עמלה 7) -> סה"כ עמלות 14.5
    {"Symbol": "GEV", "Qty": 2, "Sell_Price": 654.21, "Buy_Price": 700.00, "Date": "24.01.2026", "Fee_Total": 14.5},

    # מכירות קודמות (15.01.2026)
    {"Symbol": "PLTR", "Qty": 2, "Sell_Price": 174.00, "Buy_Price": 183.36, "Date": "15.01.2026", "Fee_Total": 14.5}, 
    {"Symbol": "AMZN", "Qty": 6, "Sell_Price": 233.80, "Buy_Price": 227.00, "Date": "15.01.2026", "Fee_Total": 14.5},
    {"Symbol": "VRTX", "Qty": 5, "Sell_Price": 432.16, "Buy_Price": 444.00, "Date": "15.01.2026", "Fee_Total": 14.0},
    
    # מכירות ישנות יותר
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "OSS",  "Qty": 165, "Sell_Price": 11.95, "Buy_Price": 11.99, "Date": "13.01.2026", "Fee_Total": 14.0},
    {"Symbol": "BIFT", "Qty": 625, "Sell_Price": 3.05, "Buy_Price": 3.21,  "Date": "13.01.2026", "Fee_Total": 14.0},
]

# תאריכי דוחות
EARNINGS_CALENDAR = {
    "VRT": "12/02/26",
    "ALB": "18/02/26"
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
# 🧠 מנוע חישובים פיננסיים
# ==========================================
def get_financial_data():
    # שער דולר
    try:
        usd_ils_ticker = yf.Ticker("ILS=X").history(period="1d")
        if not usd_ils_ticker.empty:
            rate = usd_ils_ticker['Close'].iloc[-1]
        else:
            rate = 3.65
    except:
        rate = 3.65

    symbols = [i['Symbol'] for i in CURRENT_PORTFOLIO]
    if not symbols: return pd.DataFrame(), rate, 0, 0, 0, 0, 0

    tickers = yf.Tickers(" ".join(symbols))
    
    live_rows = []
    portfolio_market_value_usd = 0 
    total_unrealized_pl_usd = 0
    fees_paid_on_open_holdings = sum([item.get('Fee', 0) for item in CURRENT_PORTFOLIO])

    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        
        last_price = 0
        prev_close = 0
        
        try:
            t = tickers.tickers[sym]
            last_price = t.fast_info.last_price
            prev_close = t.fast_info.previous_close
        except:
            pass

        if not last_price or last_price == 0:
            last_price = buy_price # Fallback
            prev_close = buy_price

        # חישובים
        cost_basis_usd = buy_price * qty
        market_val_usd = last_price * qty
        
        # שינוי יומי
        day_change = (last_price - prev_close) * qty
        day_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        
        # רווח כולל
        total_pl_native = (last_price - buy_price) * qty
        total_pl_pct = ((last_price - buy_price) / buy_price) * 100
        
        portfolio_market_value_usd += market_val_usd
        total_unrealized_pl_usd += (market_val_usd - cost_basis_usd)
        
        # אנליסטים
        try:
            info = tickers.tickers[sym].info
            rec = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
            analyst = rec if rec != "N/A" else "-"
        except:
            analyst = "-"

        def color_val(val, suffix="", prefix=""):
            c = "#2ecc71" if val >= 0 else "#e74c3c"
            return f'<span style="color:{c}; font-weight:bold;">{prefix}{val:,.2f}{suffix}</span>'

        live_rows.append({
            "Symbol": sym,
            "Qty": qty,
            "Price": f"${last_price:,.2f}",
            "Change Today": f"{color_val(day_change, '', '$')} <br><small>{color_val(day_pct, '%')}</small>",
            "Avg Cost": f"${buy_price:,.2f}",
            "Value": f"${market_val_usd:,.2f}",
            "Total P/L": f"{color_val(total_pl_native, '', '$')} <br><small>{color_val(total_pl_pct, '%')}</small>",
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
st.title("🚀 My Stocks Portfolio")

if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Analyzing Market..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data()

# חישוב שווי נקי
usd_cash = CASH_BALANCE["USD"]
ils_cash_usd = CASH_BALANCE["ILS"] / rate
total_liquid_cash_usd = usd_cash + ils_cash_usd

total_net_worth_usd = port_val + total_liquid_cash_usd
total_net_worth_ils = total_net_worth_usd * rate

# חישוב רווח כולל (כל הזמנים)
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

st.markdown("### 🏦 Account Snapshot")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
m2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f}")
m3.metric("Liquid Cash ($)", f"${total_liquid_cash_usd:,.2f}", help=f"Cash: ${usd_cash} + ₪{CASH_BALANCE['ILS']}")
m4.metric("Total Net Profit", f"${grand_total_profit:,.2f}", 
          delta_color="normal" if grand_total_profit>=0 else "inverse")

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
        cost_d = (p['Qty']*p['Buy_Price'])+fee
        buy_rows.append({"Symbol": p['Symbol'], "Date": p['Date'], "Qty": p['Qty'], 
                         "Price": f"${p['Buy_Price']:,.2f}", "Fee": fee, "Total Cost": f"${cost_d:,.2f}"})
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
