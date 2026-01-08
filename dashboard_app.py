import streamlit as st
import pandas as pd
import plotly.express as px
import os

# הגדרות דף
st.set_page_config(page_title="My AI Stock Dashboard", layout="wide")

st.title("🚀 My AI Stock Portfolio Dashboard")
st.markdown("### Live Market Analysis & AI Insights")

# נתיב לקובץ שהרובוט מייצר
# (אנחנו מחפשים אותו בתיקיית הדוחות)
FILE_PATH = "Portfolio_Reports/AI_Analysis_Report.xlsx"

# פונקציה לטעינת מידע
def load_data():
    if os.path.exists(FILE_PATH):
        return pd.read_excel(FILE_PATH)
    return None

df = load_data()

if df is not None:
    # הפרדה בין התיק לרשימת המעקב
    holdings = df[df['Type'] == 'Holdings']
    watchlist = df[df['Type'] == 'Watchlist']
    
    # --- מדדים ראשיים (KPIs) ---
    col1, col2, col3 = st.columns(3)
    
    # חישוב רווח משוקלל (הערכה)
    avg_pl = holdings['P/L %'].mean()
    total_pl_currency = 0 # (הערכה, כי לא שמרנו סכום דולרי באקסל הסופי, רק אחוזים ומחיר)

    col1.metric("Avg Portfolio P/L", f"{avg_pl:.2f}%", delta_color="normal")
    col2.metric("Active Holdings", len(holdings))
    col3.metric("Watchlist Items", len(watchlist))
    
    st.markdown("---")

    # --- חלק 1: התיק שלי ---
    st.subheader("💼 My Holdings Performance")
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # גרף עמודות צבעוני
        fig = px.bar(holdings, x='Symbol', y='P/L %', color='P/L %',
                     color_continuous_scale=['red', 'yellow', 'green'],
                     text_auto='.2f',
                     title="Profit/Loss per Stock (%)")
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        # טבלה עם המלצות AI
        st.write("Recent AI Recommendations:")
        st.dataframe(holdings[['Symbol', 'AI Summary', 'Action']], hide_index=True)

    st.markdown("---")

    # --- חלק 2: רשימת המעקב ---
    st.subheader("🔭 Watchlist Opportunities")
    
    # גרף בועות (בועה גדולה = מחיר גבוה, צבע = הפעולה המומלצת)
    fig2 = px.scatter(watchlist, x='Symbol', y='P/L %', 
                      size='Price', color='Action',
                      hover_data=['AI Summary'],
                      title="Watchlist: Price vs. Potential (Bubble Size = Price)",
                      color_discrete_map={"HOT NEWS": "gold", "UPTREND ENTRY": "green", "WATCH": "blue"})
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # כפתור רענון
    if st.button('🔄 Refresh Data'):
        st.rerun()

else:
    st.warning(f"⚠️ Report file not found at: {FILE_PATH}")
    st.info("Please run your 'ai_bot_manager.py' script first to generate the report!")