import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================
# 💾 נתוני המשתמש (Hardcoded Data)
# ==========================================

# 1. יתרות מזומן (IBKR + בנק אם תרצה)
# הוספנו 1600 ש"ח ליתרה הקודמת (4822.39 + 1600)
CASH_BALANCE = {
    "USD": 1348.40, 
    "ILS": 6422.39  
}

# 2. תיק נוכחי (כולל הקרנות החדשות מהבנק)
# הערה: לקרנות בנק שמתי עמלה 0 כרגע (כי זה לא IBKR), אם יש עמלה תעדכן
CURRENT_PORTFOLIO = [
    # --- מניות ארה"ב (IBKR) ---
    {"Symbol": "PLTR", "Qty": 2, "Buy_Price": 183.36, "Date": "18.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "AMZN", "Qty": 6, "Buy_Price": 227.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "VRT",  "Qty": 8, "Buy_Price": 163.00, "Date": "22.12.2025", "Fee": 7.5, "Currency": "USD"},
    {"Symbol": "GEV",  "Qty": 2, "Buy_Price": 700.00, "Date": "10.12.2025", "Fee": 7.5, "Currency": "USD"},
    
    # --- קרנות בנק (ישראל) ---
    # מחקה S&P 500 (1159250): קנית 10 יח' ב-23,532 ש"ח -> מחיר יחידה 2,353.2 ש"ח
    {"Symbol": "1159250.TA", "Qty": 10, "Buy_Price": 2353.20, "Date": "11.01.2026", "Fee": 0.0, "Currency": "ILS"},
    
    # מדד בנקים (1206549): קנית 244 יח' ב-26,652.67 ש"ח -> מחיר יחידה 109.23 ש"ח
    {"Symbol": "1206549.TA", "Qty": 244, "Buy_Price": 109.23, "Date": "11.01.2026", "Fee": 0.0, "Currency": "ILS"},
]

# 3. היסטוריית מכירות (כולל ההפסדים על OSS ו-BIFT)
SOLD_HISTORY = [
    {"Symbol": "RKLB", "Qty": 10, "Sell_Price": 85.00, "Buy_Price": 53.80, "Date": "08.01.2026", "Fee_Total": 15.0},
    {"Symbol": "MU",   "Qty": 2,  "Sell_Price": 325.00, "Buy_Price": 238.68, "Date": "08.01.2026", "Fee_Total": 15.0},
    # עסקאות ההפסד
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

# עמלה דיפולטיבית (לשימוש עתידי)
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
# 🧠 מנוע חישובים פיננסיים (תומך מט"ח)
# ==========================================
def get_financial_data():
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
        
        try:
            ticker_obj = tickers.tickers[sym]
            fast_info = ticker_obj.fast_info
            last_price = fast_info.last_price
            prev_close = fast_info.previous_close
            
            # זיהוי מניות ת"א (המחיר מגיע באגורות, צריך לחלק ב-100)
            if sym.endswith(".TA"):
                last_price = last_price / 100
                prev_close = prev_close / 100
            
            # המרות לדולר לחישובים הכוללים
            if currency == "ILS":
                price_in_usd = last_price / rate
                prev_close_in_usd = prev_close / rate
                buy_price_in_usd = buy_price / rate
                cost_basis_usd = buy_price_in_usd * qty
                market_val_usd = price_in_usd * qty
                
                # הצגה בטבלה (נשאיר בשקלים למניות ישראליות שיהיה ברור)
                display_price = f"₪{last_price:,.2f}"
                display_cost = f"₪{buy_price:,.2f}"
                display_val = f"₪{last_price * qty:,.2f}"
                change_symbol = "₪"
            else:
                price_in_usd = last_price
                prev_close_in_usd = prev_close
                cost_basis_usd = buy_price * qty
                market_val_usd = last_price * qty
                
                display_price = f"${last_price:,.2f}"
                display_cost = f"${buy_price:,.2f}"
                display_val = f"${market_val_usd:,.2f}"
                change_symbol = "$"

            # מידע מורחב
            try:
                info = ticker_obj.info
                target_price = info.get('targetMeanPrice', None)
                recommendation = info.get('recommendationKey', 'N/A').replace('_', ' ').upper()
                
                analyst_display = "N/A"
                if target_price:
                    # התאמת יעד אנליסטים למטבע (אם זה בשקלים)
                    current_for_calc = last_price
                    upside_pct = ((target_price - current_for_calc) / current_for_calc) * 100
                    a_color = "#2ecc71" if upside_pct > 0 else "#e74c3c"
                    arrow = "▲" if upside_pct > 0 else "▼"
                    analyst_display = f'<span style="color:{a_color}; font-weight:bold;">{recommendation}<br><small>{arrow} {upside_pct:.1f}%</small></span>'
            except:
                analyst_display = "Data Unavail."

            earnings_date = EARNINGS_CALENDAR.get(sym, "-")
            
            # חישוב שינויים
            day_change = (last_price - prev_close) * qty
            day_pct = ((last_price - prev_close) / prev_close) * 100
            
            # רווח כולל (במטבע המקור)
            total_pl_native = (last_price - buy_price) * qty
            total_pl_pct = ((last_price - buy_price) / buy_price) * 100
            
            # צבירה לסיכום דולרי
            portfolio_market_value_usd += market_val_usd
            total_unrealized_pl_usd += (market_val_usd - cost_basis_usd)

            def color_val(val, suffix="", prefix=""):
                c = "#2ecc71" if val >= 0 else "#e74c3c"
                return f'<span style="color:{c}; font-weight:bold;">{prefix}{val:,.2f}{suffix}</span>'

            live_rows.append({
                "Symbol": sym.replace(".TA", " (IL)"), # הצגה יפה יותר
                "Qty": qty,
                "Price": display_price,
                "Change": color_val(day_change, "", change_symbol),
                "Cost": display_cost,
                "Value": display_val,
                "Daily P/L": f"{color_val(day_change, '', change_symbol)} <br><small>{color_val(day_pct, '%')}</small>",
                "Total P/L": f"{color_val(total_pl_native, '', change_symbol)} <br><small>{color_val(total_pl_pct, '%')}</small>",
                "Analysts": analyst_display,
                "Next Report": earnings_date
            })
            
        except Exception as e:
            live_rows.append({"Symbol": sym, "Price": "Error"})

    # --- חישוב היסטורי (מכירות) ---
    total_realized_pl_net_usd = 0
    fees_paid_on_sold_total = 0
    
    for s in SOLD_HISTORY:
        gross_profit = (s['Sell_Price'] - s['Buy_Price']) * s['Qty']
        trade_fees = s.get('Fee_Total', CURRENT_FEE * 2)
        net_profit = gross_profit - trade_fees
        total_realized_pl_net_usd += net_profit
        fees_paid_on_sold_total += trade_fees

    total_fees_lifetime = fees_paid_on_open_holdings + fees_paid_on_sold_total
    
    return pd.DataFrame(live_rows), rate, portfolio_market_value_usd, total_unrealized_pl_usd, total_realized_pl_net_usd, total_fees_lifetime, fees_paid_on_open_holdings

# ==========================================
# 📱 ממשק משתמש
# ==========================================
st.title("🌍 My Global Portfolio")

if st.button("🔄 REFRESH LIVE DATA", type="primary", use_container_width=True):
    st.rerun()

with st.spinner("Fetching Global Market Data..."):
    df_live, rate, port_val, unrealized_pl, realized_pl_net, total_fees, fees_open = get_financial_data()

# --- חישובים ---
# סך הכל מזומן בדולרים (ממיר את השקלים לדולר לצורך חישוב כולל)
usd_cash = CASH_BALANCE["USD"]
ils_cash_usd = CASH_BALANCE["ILS"] / rate
total_cash_usd = usd_cash + ils_cash_usd

# שווי נקי כולל (מניות ארה"ב + מניות ישראל בדולרים + מזומן)
total_net_worth_usd = port_val + total_cash_usd
total_net_worth_ils = total_net_worth_usd * rate

# שורת המחץ
grand_total_profit = unrealized_pl + realized_pl_net - fees_open

# --- תצוגת מדדים ---
st.markdown("### 🏦 Account Snapshot (Combined)")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Net Worth ($)", f"${total_net_worth_usd:,.2f}")
m2.metric("Net Worth (₪)", f"₪{total_net_worth_ils:,.2f}", f"Rate: {rate:.2f}")
m3.metric("Liquid Cash ($)", f"${total_cash_usd:,.2f}")
m4.metric("Total Net Profit (All Time)", f"${grand_total_profit:,.2f}", 
          delta_color="normal" if grand_total_profit>=0 else "inverse")

st.caption(f"Lifetime Fees Paid: ${total_fees:,.2f} | Open Positions Value: ${port_val:,.2f}")
st.markdown("---")

# --- לשוניות ---
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
        sym_display = p['Symbol'].replace(".TA", " (IL)")
        price_display = f"₪{p['Buy_Price']:,.2f}" if curr == "ILS" else f"${p['Buy_Price']:,.2f}"
        cost_display = f"₪{(p['Qty']*p['Buy_Price'])+fee:,.2f}" if curr == "ILS" else f"${(p['Qty']*p['Buy_Price'])+fee:,.2f}"
        
        buy_rows.append({
            "Symbol": sym_display, "Date": p['Date'], "Qty": p['Qty'], 
            "Price": price_display, "Fee": fee, "Total Cost": cost_display
        })
    # היסטוריה
    for s in SOLD_HISTORY:
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
