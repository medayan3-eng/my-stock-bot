import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש (Hardcoded Data)
# ==========================================

# 1. יתרות מזומן מעודכנות
# (חושב מחדש: יתרה קודמת פחות הפסדי מסחר ועמלות של אתמול + הפקדה לשקלים)
CASH_BALANCE = {
    "USD": 1348.40, 
    "ILS": 4822.39  
}

# 2. תיק נוכחי (החזקות פתוחות)
# הוספתי את עמלת הקנייה ההיסטורית (7.5$) לכל מניה כדי שהחישוב יהיה מדויק
CURRENT_PORTFOLIO = [
    {"Symbol": "PLTR", "Qty": 2, "Buy_Price": 183.36, "Date": "18.12.2025", "Fee": 7.5},
    {"Symbol": "AMZN", "Qty": 6, "Buy_Price": 227.00, "Date": "22.12.2025", "Fee": 7.5},
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025", "Fee": 7.5},
    {"Symbol": "GEV",  "Qty": 2, "Buy_Price": 700.00, "Date": "10.12.2025", "Fee": 7.5},
]

# 3. היסטוריית מכירות (סגורות)
# כאן אנחנו מתעדים את העמלה שהייתה בפועל באותו זמן (7.5 לכל צד = 15 טוטאל)
SOLD_HISTORY = [
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    # העסקאות של אתמול (הפסדים)
    {"Symbol": "OSS",  "Qty": 165, "Sell_Price": 11.95, "Buy_Price": 11.99, "Date": "13.01.2026", "Fee_Total": 15.0},
    {"Symbol": "BIFT", "Qty": 625, "Sell_Price": 3.05, "Buy_Price": 3.21,  "Date": "13.01.2026", "Fee_Total": 15.0},
]

# 📅 יומן דוחות
EARNINGS_CALENDAR = {
    "AMZN": "06/02/26",
    "PLTR": "03/02/26",
    "VRT":  "12/02/26",
    "GEV":  "28/01/26"
}

# עמלה חדשה מעכשיו והלאה (לסימולציות ולעסקאות עתידיות שתוסיף בלי לציין עמלה)
CURRENT_FEE = 7.0 

# ==========================================
# ⚙️ הגדרות תצוגה
# ==========================================
st.set_page_config(page_title="Pro Analyst Portfolio", layout="wide", page_icon="🏦")
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
    try:
        usd_ils = yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_ils = 3.65

    symbols = [i['Symbol'] for i in CURRENT_PORTFOLIO]
    if not symbols: return pd.DataFrame(), usd_ils, 0, 0, 0, 0

    tickers = yf.Tickers(" ".join(symbols))
    
    live_rows = []
    portfolio_market_value = 0 
    total_unrealized_pl = 0
    
    # חישוב עמלות ששולמו על התיק הפתוח (לפי מה שרשום לכל מניה)
    fees_paid_on_open_holdings = sum([item.get('Fee', CURRENT_FEE) for item in CURRENT_PORTFOLIO])

    for item in CURRENT_PORTFOLIO:
        sym = item['Symbol']
        qty = item['Qty']
        buy_price = item['Buy_Price']
        
        try:
            ticker_obj = tickers.tickers[sym]
            fast_info = ticker_obj.fast_info
            last_price = fast_info.last_price
            prev_close = fast_info.previous_close
            
            # מידע מורחב
            try:
                info = ticker_obj.info
                bid = info.get('bid', 0)
                ask = info.get('ask', 0)
                d_high = info.get('dayHigh', 0)
                d_low = info.get('dayLow', 0)
                target_price = info.get('targetMeanPrice', None)
                recommendation = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
                
                analyst_display = "N/A"
                if target_price:
                    upside_pct = ((target_price - last_price) / last_price) * 100
                    a_color = "#2ecc71" if upside_pct > 0 else "#e74c3c"
                    arrow = "▲" if upside_pct > 0 else "▼"
                    if -1 < upside_pct < 1: a_color = "gray"
                    analyst_display = f'<span style="color:{a_color}; font-weight:bold;">{recommendation}<br><small>{arrow} {upside_pct:.1f}% (Target: ${target_price})</small></span>'
            except:
                bid, ask, d_high, d_low = 0, 0, 0, 0
                analyst_display = "Data Unavail."

            earnings_date = EARNINGS_CALENDAR.get(sym, "-")

            # חישובים
            market_val = last_price * qty
            cost_basis = buy_price * qty
            
            day_change = (last_price - prev_close) * qty
            day_pct = ((last_price - prev_close) / prev_close) * 100
            
            total_pl = market_val - cost_basis
            total_pl_pct = (total_pl / cost_basis) * 100
            
            portfolio_market_value += market_val
            total_unrealized_pl += total_pl

            def color_val(val, suffix=""):
                c = "#2ecc71" if val >= 0 else "#e74c3c"
                return f'<span style="color:{c}; font-weight:bold;">{val:,.2f}{suffix}</span>'

            live_rows.append({
                "Symbol": sym,
                "Qty": qty,
                "Last Price": f"${last_price:.2f}",
                "Change ($)": color_val(last_price - prev_close, "$"),
                "Bid / Ask": f"{bid:.2f} / {ask:.2f}",
                "Day Range": f"{d_low:.2f}-{d_high:.2f}",
                "Cost": f"${buy_price:.2f}",
                "Value": f"${market_val:,.2f}",
                "Daily P/L": f"{color_val(day_change, '$')} <br><small>{color_val(day_pct, '%')}</small>",
                "Total P/L": f"{color_val(total_pl, '$')} <br><small>{color_val(total_pl_pct, '%')}</small>",
                "Analysts": analyst_display,
                "Next Report": earnings_date
            })
            
        except Exception as e:
            live_rows.append({"Symbol": sym, "Last Price": "Error"})

    # --- חישוב היסטורי (מכירות) ---
    total_realized_pl_net = 0
    fees_paid_on_sold_total = 0
    
    for s in SOLD_HISTORY:
        gross_profit = (s['Sell_Price'] - s['Buy_Price']) * s['Qty']
        # שימוש בעמלה הספציפית לעסקה אם קיימת, אחרת ברירת מחדל כפולה
        trade_fees = s.get('Fee_Total', CURRENT_FEE * 2)
        
        net_profit = gross_profit - trade_fees
        total_realized_pl_net += net_profit
        fees_paid_on_sold_total += trade_fees

    total_fees_lifetime = fees_paid_on_open_holdings + fees_paid_on_sold_total
    
    return pd.DataFrame(live_rows), usd_ils, portfolio_market_value, total_unrealized_pl, total_realized_pl_net, total_fees_lifetime, fees_paid_on_open_holdings

# ==========================================
# 📱 ממשק משתמש
# ==========================================
st.title("🏛️ My Financial Command Center")

if st.button("🔄 REFRESH LIVE DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Talking to Analysts & Fetching Reports..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data()

# --- חישובים ---
usd_cash = CASH_BALANCE["USD"]
ils_cash_usd = CASH_BALANCE["ILS"] / rate
total_net_worth_usd = port_val + usd_cash + ils_cash_usd
total_net_worth_ils = total_net_worth_usd * rate
buying_power = usd_cash + ils_cash_usd

# שורת המחץ: רווח פתוח + רווח סגור נקי - עמלות ששולמו על הפתוח
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

# --- תצוגת מדדים ---
st.markdown("### 🏦 Account Snapshot")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
m2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f}")
m3.metric("Buying Power", f"${buying_power:,.2f}")
m4.metric("Total Net Profit (All Time)", f"${grand_total_profit:,.2f}", 
          delta_color="normal" if grand_total_profit>=0 else "inverse")

st.caption(f"Lifetime Fees Paid: ${total_fees:,.2f} | (Fees include historic $7.5 & new $7.0 rates)")
st.markdown("---")

# --- לשוניות ---
tab1, tab2, tab3 = st.tabs(["📊 Live Portfolio", "🧾 Buy Log", "💰 Realized P/L"])

with tab1:
    if not df_live.empty:
        st.write(df_live.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No active holdings.")

with tab2:
    buy_rows = []
    # מציג את העמלה שהייתה בפועל בקנייה
    for p in CURRENT_PORTFOLIO:
        fee = p.get('Fee', CURRENT_FEE)
        buy_rows.append({
            "Symbol": p['Symbol'], "Date": p['Date'], "Qty": p['Qty'], 
            "Price": f"${p['Buy_Price']:.2f}", "Fee": f"${fee:.2f}",
            "Total Cost": f"${(p['Qty']*p['Buy_Price'])+fee:,.2f}"
        })
    for s in SOLD_HISTORY:
        # בהיסטוריה שמרנו Fee_Total, אז נניח חצי מזה לקנייה
        fee = s.get('Fee_Total', CURRENT_FEE * 2) / 2
        buy_rows.append({
            "Symbol": f"{s['Symbol']} (Sold)", "Date": s['Date'], "Qty": s['Qty'], 
            "Price": f"${s['Buy_Price']:.2f}", "Fee": f"${fee:.2f}",
            "Total Cost": f"${(s['Qty']*s['Buy_Price'])+fee:,.2f}"
        })
    st.dataframe(pd.DataFrame(buy_rows), use_container_width=True)

with tab3:
    st.subheader("💸 Net Realized Profit (After Fees)")
    sold_rows = []
    for s in SOLD_HISTORY:
        buy_cost = s['Buy_Price'] * s['Qty']
        sell_rev = s['Sell_Price'] * s['Qty']
        # עמלה כוללת (קניה+מכירה)
        total_fee = s.get('Fee_Total', CURRENT_FEE * 2)
        
        net_pl = sell_rev - buy_cost - total_fee
        color = "green" if net_pl > 0 else "red"
        sold_rows.append({
            "Symbol": s['Symbol'], "Qty": s['Qty'],
            "Buy Price": f"${s['Buy_Price']:.2f}", "Sell Price": f"${s['Sell_Price']:.2f}",
            "Total Fees": f"${total_fee:.2f}",
            "Net Profit ($)": f'<span style="color:{color}; font-weight:bold;">${net_pl:,.2f}</span>'
        })
    st.write(pd.DataFrame(sold_rows).to_html(escape=False, index=False), unsafe_allow_html=True)
