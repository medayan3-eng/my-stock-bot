import streamlit as st
import pandas as pd
import plotly.express as px
import os
import yfinance as yf
import google.generativeai as genai
from datetime import datetime

# ==========================================
# ⚙️ הגדרות
# ==========================================
st.set_page_config(page_title="My AI Stock Dashboard", layout="wide", page_icon="🚀")

# טעינת המפתח
try:
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    GEMINI_KEY = None

# הגדרת מודל חכמה (מנסה כמה אפשרויות)
model = None
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # ננסה קודם את המודל המהיר, אם לא קיים נלך על הקלאסי
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        model = genai.GenerativeModel('gemini-pro')

CONFIG_FILE = "my_stock_config.xlsx"
REPORT_FILE = "AI_Analysis_Report.xlsx"

# ==========================================
# 🧠 פונקציות
# ==========================================
def analyze_with_ai(ticker, news_list):
    if not model: return "AI Not Connected", 0
    if not news_list: return "No News", 0
    
    headlines = [n.get('title', '') for n in news_list[:3]]
    text = ". ".join(headlines)
    
    # הנחיה ל-AI (קצרה וממוקדת)
    prompt = f"Stock {ticker}: '{text}'. Summary (max 10 words) | Score (-1 to 1)."
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if "|" in content:
            return content.split("|")[0], float(content.split("|")[1])
        return content, 0
    except Exception as e:
        # במקרה של שגיאה, נחזיר הודעה נקייה יותר
        return "Analysis Skipped", 0

def get_sp500_return():
    try:
        spy = yf.Ticker("^GSPC")
        hist = spy.history(period="1y")
        start = hist['Close'].iloc[0]
        end = hist['Close'].iloc[-1]
        return ((end - start) / start) * 100
    except:
        return 0.0

def run_full_analysis():
    if not os.path.exists(CONFIG_FILE):
        st.error(f"❌ '{CONFIG_FILE}' not found on GitHub!")
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
    
    new_df = pd.DataFrame(report_data)
    new_df.to_excel(REPORT_FILE, index=False)
    return new_df

# ==========================================
# 📊 תצוגה
# ==========================================
st.title("🚀 My AI Cloud Dashboard")
st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if st.button("🔄 Run AI Analysis Now"):
    with st.spinner("Connecting to Google Brain..."):
        df = run_full_analysis()
        st.success("Data Updated!")
        st.rerun()

if os.path.exists(REPORT_FILE):
    df = pd.read_excel(REPORT_FILE)
    holdings = df[df['Type'] == 'Holdings']
    watchlist = df[df['Type'] == 'Watchlist']
    
    # 1. השוואה לשוק
    my_return = holdings['P/L %'].mean()
    market_return = get_sp500_return()
    diff = my_return - market_return
    
    c1, c2, c3 = st.columns(3)
    c1.metric("My Portfolio", f"{my_return:.2f}%")
    c2.metric("S&P 500 (1Y)", f"{market_return:.2f}%")
    c3.metric("Beating Market?", f"{diff:.2f}%", "YES 🏆" if diff>0 else "NO 📉", delta_color="normal")
    
    st.markdown("---")
    
    # 2. גרפים
    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        st.subheader("💼 Holdings P/L")
        fig = px.bar(holdings, x='Symbol', y='P/L %', color='P/L %', 
                     color_continuous_scale=['red', 'yellow', 'green'], text_auto='.1f')
        st.plotly_chart(fig, use_container_width=True)
    
    with col_g2:
        st.subheader("🧠 AI Insights")
        st.dataframe(holdings[['Symbol', 'AI Summary', 'Action']], hide_index=True, use_container_width=True)

    # 3. רשימת מעקב
    st.subheader("🔭 Watchlist Radar")
    if not watchlist.empty:
        fig2 = px.scatter(watchlist, x='Symbol', y='Price', size='Price', color='Action',
                          hover_data=['AI Summary'], title="Market Opportunities")
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("👋 Click the button above to start!")
