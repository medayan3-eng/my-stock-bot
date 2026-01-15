import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש
# ==========================================

CASH_BALANCE = {
    "USD": -878.60, 
    "ILS": 6422.39  
}

CURRENT_PORTFOLIO = [
    # --- מניות ארה"ב ---
    {"Symbol": "PLTR", "Qty": 2, "Buy_Price": 183.36, "Date": "18.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "AMZN", "Qty": 6, "Buy_Price": 227.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "GEV",  "Qty": 2, "Buy_Price": 700.00, "Date": "10.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "VRTX", "Qty": 5, "Buy_Price": 444.00, "Date": "15.01.2026", "Fee": 7.0, "Currency": "USD"},
    
    # --- קרנות בנק (ישראל) ---
    # MTF S&P 500 (מספר 1159250)
    {"Symbol": "1159250.TA", "Name": "MTF S&P 500 (IL)", 
     "Qty": 10, "Buy_Price": 2353.10, "Date": "11.01.2026", "Fee": 0.0, "Currency": "ILS"},
    
    # MTF Banks 5 (מספר 1206549)
    {"Symbol": "1206549.TA", "Name": "MTF Banks 5 (IL)",
     "Qty": 244, "Buy_Price": 109.232, "Date": "11.01.2026", "Fee": 0.0, "Currency": "ILS"},
]

SOLD_HISTORY = [
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "OSS",  "Qty": 165, "Sell_Price": 11.95, "Buy_Price": 11.99, "Date": "13.01.2026", "Fee_Total": 15.0},
    {"Symbol": "BIFT", "Qty": 625, "Sell_Price": 3.05, "Buy_Price": 3.21,  "Date": "13.01.2026", "Fee_Total": 15.0},
]

EARNINGS_CALENDAR = {
    "AMZN": "06/02/26",
    "PLTR": "03/02/26",
    "VRT":  "12/02/26",
    "GEV":  "28/01/26",
    "VRTX": "05/02/26"
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
    # משיכת שער דולר
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
        currency = item.get("Currency", "USD")
        display_name = item.get("Name", sym.replace(".TA", " (IL)"))
        
        last_price = 0
        prev_close = 0
        
        # 1. בדיקה אם יש מחיר ידני (מהסיידבר)
        # המשתמש יכול להזין בשקלים או באגורות, הקוד יתמודד
        manual_val = manual_prices.get(sym, 0)
        
        if manual_val > 0:
            last_price = manual_val
            # אם המשתמש הזין באגורות (מספר גדול מ-500 בדרך כלל לקרנות האלו), נמיר לשקלים
            if sym.endswith(".TA") and last_price > 500: 
                last_price = last_price / 100
                
            prev_close = last_price # באינפוט ידני אין לנו היסטוריה
        else:
            # 2. משיכה מיאהו (אם אין ידני)
            try:
                t = tickers.tickers[sym]
                # מנסים למשוך היסטוריה קצרה במקום fast_info שקורס לקרנות האלו
                hist = t.history(period="5d")
                if not hist.empty:
                    last_price = hist['Close'].iloc[-1]
                    if len(hist) > 1:
                        prev_close = hist['Close'].iloc[-2]
                    else:
                        prev_close = last_price
                    
                    # המרה מאגורות לשקלים
                    if sym.endswith(".TA"):
                        last_price /= 100
                        prev_close /= 100
            except:
                pass

        # מנגנון הגנה: אם אין מחיר, לא שוברים את השורה!
        # מציגים את השורה עם הערה שצריך לעדכן
        price_missing = False
        if not last_price or last_price == 0:
            last_price = buy_price # כדי שהחישוב לא יקרוס
            prev_close = buy_price
            price_missing = True

        # --- חישובים ---
        if currency == "ILS":
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
        
        # שינוי כולל
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

        # עיצוב מיוחד אם המחיר חסר
        if price_missing:
            display_price = "⚠️ Update in Sidebar"
            display_val = "Pending..."
            analyst = "-"
            day_change = 0
            day_pct = 0
            total_pl_native = 0
            total_pl_pct = 0

        # אייקון סטטוס
        status = ""
        if manual_val > 0: status = "✏️ (Manual)"
        elif price_missing: status = "❌ (No Data)"

        def color_val(val, suffix="", prefix=""):
            c = "#2ecc71" if val >= 0 else "#e74c3c"
            return f'<span style="color:{c}; font-weight:bold;">{prefix}{val:,.2f}{suffix}</span>'

        live_rows.append({
            "Symbol": f"{display_name} {status}",
            "Qty": qty,
            "Price": display_price,
            "Change Today": f"{color_val(day_change, '', change_symbol)} <br><small>{color_val(day_pct, '%')}</small>" if not price_missing else "-",
            "Avg Cost": display_cost,
            "Value": display_val,
            "Total P/L": f"{color_val(total_pl_native, '', change_symbol)} <br><small>{color_val(total_pl_pct, '%')}</small>" if not price_missing else "-",
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
# 📱 ממשק
# ==========================================
st.title("🌍 My Global Portfolio")

# --- סרגל צד לתיקון ידני ---
# זה הפתרון לקרנות הישראליות!
st.sidebar.header("🛠️ Israeli Funds Update")
st.sidebar.info("Yahoo Finance sometimes blocks Israeli fund data. Enter price manually here from your bank app if needed.")
manual_prices = {}
for p in CURRENT_PORTFOLIO:
    if p.get("Currency") == "ILS":
        sym = p['Symbol']
        name = p.get("Name", sym)
        # ברירת מחדל 0
        val = st.sidebar.number_input(f"{name} (Price in ₪ or Agorot)", min_value=0.0, value=0.0, step=0.1)
        manual_prices[sym] = val

if st.button("🔄 REFRESH LIVE DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Calculating Portfolio..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data(manual_prices)

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
        st.caption("Tip: Use the Sidebar (top-left arrow on mobile) to update Israeli funds if they show 'Update in Sidebar'.")
        st.write(df_live.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No active holdings.")

with tab2:
    buy_rows = []
    for p in CURRENT_PORTFOLIO:
        fee = p.get('Fee', 0)
        curr = p.get("Currency", "USD")
        sym = p.get("Name", p['Symbol'].replace(".TA", " (IL)"))
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
