import streamlit as st
import pandas as pd
import plotly.express as px
import os
import yfinance as yf
import google.generativeai as genai
from datetime import datetime

# ==========================================
# ⚙️ הגדרות וטעינת סודות מהענן
# ==========================================
st.set_page_config(page_title="My AI Stock Dashboard", layout="wide", page_icon="🚀")

# בדיקה אם אנחנו בענן (קורא מה-Secrets) או במחשב מקומי
try:
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    GEMINI_KEY = "YOUR_LOCAL_KEY" # למקרה שאתה מריץ במחשב בלי secrets

# הגדרת ה-AI
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

CONFIG_FILE = "my_stock_config.xlsx"
REPORT_FILE = "AI_Analysis_Report.xlsx"

# ==========================================
# 🧠 פונקציות המוח (הרובוט)
# ==========================================
def analyze_with_ai(ticker, news_list):
    if not news_list: return "No News", 0
    headlines = [n.get('title', '') for n in news_list[:3]]
    text = ". ".join(headlines)
    
    prompt = f"Analyze stock {ticker} headlines: '{text}'. 1 sentence summary | Score -1 to 1."
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if "|" in content:
            return content.split("|")[0], float(content.split("|")[1])
        return content, 0
    except:
        return "AI Error", 0

def run_full_analysis():
    # טעינת רשימת המניות
    if not os.path.exists(CONFIG_FILE):
        st.error(f"❌ Config file '{CONFIG_FILE}' missing! Please upload it to GitHub.")
        return None

    df_config = pd.read_excel(CONFIG_FILE)
    report_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(df_config)
    
    for i, row in df_config.iterrows():
        ticker = row['Symbol']
        status_text.text(f"🤖 AI Analyzing: {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if hist.empty: continue
            
            price = hist['Close'].iloc[-1]
            ai_sum, ai_score = analyze_with_ai(ticker, stock.news)
            
            # לוגיקה
            pl_percent = 0
            action = "WATCH"
            
            if row['Type'] == 'Holdings':
                buy_price = row['Buy_Price']
                pl_percent = ((price - buy_price) / buy_price) * 100
                if pl_percent > 15: action = "💰 TAKE PROFIT"
                elif pl_percent < -5 and ai_score > 0: action = "♻️ BUY DIP"
                else: action = "HOLD"
            else:
                if ai_score > 0.5: action = "🚀 OPPORTUNITY"
            
            report_data.append({
                "Symbol": ticker, "Type": row['Type'], "Price": price,
                "P/L %": pl_percent, "AI Summary": ai_sum, "Action": action
            })
            
        except Exception as e:
            print(f"Error {ticker}: {e}")
        
        progress_bar.progress((i + 1) / total)

    status_text.text("✅ Analysis Complete!")
    progress_bar.empty()
    
    # שמירת התוצאות לקובץ זמני
    new_df = pd.DataFrame(report_data)
    new_df.to_excel(REPORT_FILE, index=False)
    return new_df

# ==========================================
# 📊 תצוגת הדשבורד (UI)
# ==========================================
st.title("🚀 My AI Cloud Dashboard")
st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# כפתור הפעלה ידני
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("🔄 Run AI Analysis Now"):
        with st.spinner("Connecting to Google Brain..."):
            df = run_full_analysis()
            st.success("New data generated!")
            st.rerun()

# טעינת נתונים
if os.path.exists(REPORT_FILE):
    df = pd.read_excel(REPORT_FILE)
    
    # KPIs
    holdings = df[df['Type'] == 'Holdings']
    watchlist = df[df['Type'] == 'Watchlist']
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Portfolio Assets", len(holdings))
    kpi2.metric("Watchlist Items", len(watchlist))
    try:
        avg_pl = holdings['P/L %'].mean()
        kpi1.metric("Avg P/L", f"{avg_pl:.2f}%", delta_color="normal")
    except: pass

    st.markdown("---")
    
    # גרף התיק
    st.subheader("💼 Portfolio Performance")
    fig = px.bar(holdings, x='Symbol', y='P/L %', color='P/L %', 
                 color_continuous_scale=['red', 'yellow', 'green'], title="Holdings P/L")
    st.plotly_chart(fig, use_container_width=True)
    
    # טבלת AI
    st.subheader("🧠 AI Insights")
    st.dataframe(holdings[['Symbol', 'AI Summary', 'Action']], hide_index=True, use_container_width=True)

    # גרף הזדמנויות
    st.subheader("🔭 Watchlist Radar")
    if not watchlist.empty:
        fig2 = px.scatter(watchlist, x='Symbol', y='Price', size='Price', color='Action',
                          hover_data=['AI Summary'], title="Opportunities")
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("⚠️ No report found yet. Click the 'Run AI Analysis Now' button above to start!")
