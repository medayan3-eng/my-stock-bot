import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש (Hardcoded Data)
# ==========================================

# 1. יתרות מזומן (מחושב לאחר כל הקניות והמכירות האחרונות)
# התחלה: 7,183.56
# רווח/הפסד ממימושים (KLAC, DIS, BARK, INOD): -172.07
# עלות קניית WFRD (כולל עמלה): -2,543.65
# עלות קניית SMH (כולל עמלה): -4,455.40
# יתרה סופית: 12.44
CASH_BALANCE = {
    "USD": 12.44, 
    "ILS": 798.45 
}

# 2. התיק הנוכחי (פוזיציות פתוחות)
CURRENT_PORTFOLIO = [
    # קניות מאתמול (נניח 03.02.2026)
    {"Symbol": "WFRD", "Qty": 27, "Buy_Price": 93.95, "Date": "03.02.2026", "Fee": 7.0},
    {"Symbol": "SMH",  "Qty": 11, "Buy_Price": 404.40, "Date": "03.02.2026", "Fee": 7.0},
]

# 3. היסטוריית מכירות (סגורות)
SOLD_HISTORY = [
    # --- עסקאות מלפני 3 ימים (נניח 01.02.2026) ---
    # KLAC: קנייה 1433 | מכירה 1407.74 | כמות 2 | עמלה 14
    {"Symbol": "KLAC", "Qty": 2, "Sell_Price": 1407.74, "Buy_Price": 1433.00, "Date": "01.02.2026", "Fee_Total": 14.0},

    # DIS: קנייה 105 | מכירה 4300.80/40 = 107.52 | כמות 40 | עמלה 14
    {"Symbol": "DIS", "Qty": 40, "Sell_Price": 107.52, "Buy_Price": 105.00, "Date": "01.02.2026", "Fee_Total": 14.0},

    # BARK: קנייה 0.89 | מכירה 0.8501 | כמות 2500 | עמלה 14
    {"Symbol": "BARK", "Qty": 2500, "Sell_Price": 0.8501, "Buy_Price": 0.89, "Date": "01.02.2026", "Fee_Total": 14.0},

    # INOD: קנייה 56.3 | מכירה 54.82 | כמות 45 | עמלה 14
    {"Symbol": "INOD", "Qty": 45, "Sell_Price": 54.82, "Buy_Price": 56.30, "Date": "01.02.2026", "Fee_Total": 14.0},

    # --- עסקאות קודמות ---
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

# תאריכי דוחות משוערים
EARNINGS_CALENDAR = {
    "WFRD": "04/02/26", # משוער
    "SMH": "N/A" # תעודת סל, אין דוחות
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
# 🧠 מנוע חישובים
# ==========================================
def get_financial_data():
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
        # אם התיק ריק, מחזירים רק נתונים בסיסיים והיסטוריה
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
        except: pass

        if not last_price or last_price == 0:
            last_price = buy_price
            prev_close = buy_price

        cost_basis_usd = buy_price * qty
        market_val_usd = last_price * qty
        day_change = (last_price - prev_close) * qty
        day_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        total_pl_native = (last_price - buy_price) * qty
        total_pl_pct = ((last_price - buy_price) / buy_price) * 100
        
        portfolio_market_value_usd += market_val_usd
        total_unrealized_pl_usd += (market_val_usd - cost_basis_usd)
        
        analyst = "-"
        try:
            info = tickers.tickers[sym].info
            rec = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
            analyst = rec if rec != "N/A" else "-"
        except: pass

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

    # היסטוריה
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

with st.spinner("Connecting to Market..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data()

usd_cash = CASH_BALANCE["USD"]
ils_cash_usd = CASH_BALANCE["ILS"] / rate
total_liquid_cash_usd = usd_cash + ils_cash_usd

total_net_worth_usd = port_val + total_liquid_cash_usd
total_net_worth_ils = total_net_worth_usd * rate
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

invested_capital = total_net_worth_usd - grand_total_profit
portfolio_return_pct = (grand_total_profit / invested_capital) * 100 if invested_capital > 0 else 0

st.markdown("### 🏦 Account Snapshot")

c1, c2, c3 = st.columns(3)
c1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
color_roi = "normal" if portfolio_return_pct >= 0 else "inverse"
c2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Return: {portfolio_return_pct:.2f}%", delta_color=color_roi)
c3.metric("Live USD Rate", f"₪{rate:.3f}")

st.markdown("---")

c4, c5, c6 = st.columns(3)
c4.metric("Total Net Profit", f"${grand_total_profit:,.2f}", delta_color="normal" if grand_total_profit>=0 else "inverse")
c5.metric("Liquid Cash", f"${total_liquid_cash_usd:,.2f}", help=f"Cash: ${usd_cash} + ₪{CASH_BALANCE['ILS']}")
c6.metric("Realized Profit", f"${realized_pl_net:,.2f}", delta_color="normal" if realized_pl_net >=0 else "inverse")

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
    if buy_rows:
        st.dataframe(pd.DataFrame(buy_rows), use_container_width=True)
    else:
        st.caption("No open positions.")

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
    
    total_realized_color = "green" if realized_pl_net >= 0 else "red"
    st.markdown(f"""
    <div style="text-align: center; padding: 10px; border: 2px solid #ddd; border-radius: 10px; background-color: #f0f2f6;">
        <h3 style="margin:0;">Total Realized Profit</h3>
        <h1 style="color: {total_realized_color}; margin:0;">${realized_pl_net:,.2f}</h1>
        <small>After all fees</small>
    </div>
    """, unsafe_allow_html=True)
