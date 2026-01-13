import streamlit as st
import pandas as pd
import yfinance as yf
import google.generativeai as genai
from datetime import datetime

# ==========================================
# 📝 כאן אתה מעדכן את הנתונים שלך! (במקום אקסל)
# ==========================================
MY_PORTFOLIO = [
    # --- מזומן (עו"ש) ---
    {"Symbol": "USD", "Qty": 1500, "Buy_Price": 1, "Type": "Cash", "Date": "Today"},
    {"Symbol": "ILS", "Qty": 5000, "Buy_Price": 1, "Type": "Cash", "Date": "Today"},

    # --- מניות שקנית (Holdings) ---
    # הפורמט: סימול, כמות, מחיר קנייה ממוצע, סוג, תאריך קנייה
    {"Symbol": "PLTR", "Qty": 2,  "Buy_Price": 183.36, "Type": "Holdings", "Date": "18.12.2025"},
    {"Symbol": "AMZN", "Qty": 6,  "Buy_Price": 227.00, "Type": "Holdings", "Date": "22.12.2025"},
    {"Symbol": "VRT",  "Qty": 8,  "Buy_Price": 163.00, "Type": "Holdings", "Date": "22.12.2025"},
    {"Symbol": "GEV",  "Qty": 2,  "Buy_Price": 700.00, "Type": "Holdings", "Date": "10.12.2025"},
    
    # --- מניות למעקב בלבד (Watchlist) ---
    # שים כמות 0 ומחיר 0
    {"Symbol": "NVDA", "Qty": 0, "Buy_Price": 0, "Type": "Watchlist", "Date": "-"},
    {"Symbol": "TSLA", "Qty": 0, "Buy_Price": 0, "Type": "Watchlist", "Date": "-"},
    {"Symbol": "GOOGL","Qty": 0, "Buy_Price": 0, "Type": "Watchlist", "Date": "-"},
]

# ==========================================
# ⚙️ הגדרות מערכת
# ==========================================
st.set_page_config(page_title="My Portfolio App", layout="wide", page_icon="📱")

# הסתרת אלמנטים מיותרים
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)

# חיבור ל-AI
try:
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_KEY)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        model = genai.GenerativeModel('gemini-pro')
except:
    model = None

# ==========================================
# 🧠 המוח (פונקציות)
# ==========================================
def get_usd_ils_rate():
    try:
        return yf.Ticker("ILS=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 3.65

def analyze_stock(ticker, type_):
    # חיסכון: לא מנתח מזומן או מניות מעקב רחוקות
    if type_ == "Cash": return "Liquid", 0
    if not model: return "No AI", 0
    
    try:
        news = yf.Ticker(ticker).news[:2]
        if not news: return "No News", 0
        
        txt = ". ".join([n['title'] for n in news])
        prompt = f"Stock {ticker}: '{txt}'. 3-word summary | Score -1 to 1."
        res = model.generate_content(prompt).text.strip()
        
        if "|" in res:
            return res.split("|")[0], float(res.split("|")[1])
        return res, 0
    except:
        return "Info N/A", 0

def load_data():
    # המרת הרשימה הידנית לטבלה של פייתון
    df = pd.DataFrame(MY_PORTFOLIO)
    rate = get_usd_ils_rate()
    today = datetime.now().strftime("%d/%m/%Y")
    
    final_data = []
    
    for _, row in df.iterrows():
        symbol = row['Symbol']
        qty = row['Qty']
        b_price = row['Buy_Price']
        p_type = row['Type']
        
        # --- טיפול במזומן ---
        if p_type == "Cash":
            val_usd = qty if symbol == "USD" else qty / rate
            val_ils = qty * rate if symbol == "USD" else qty
            final_data.append({
                "Symbol": f"💵 {symbol}",
                "Qty": qty,
                "Price": 1,
                "Value ($)": val_usd,
                "Value (₪)": val_ils,
                "Change %": 0,
                "AI": "Liquid",
                "Action": "-",
                "Type": "Cash",
                "Date": today
            })
            continue

        # --- טיפול במניות ---
        try:
            current_price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
            ai_txt, ai_score = analyze_stock(symbol, p_type)
            
            pl_pct = ((current_price - b_price) / b_price * 100) if b_price > 0 else 0
            
            # לוגיקת המלצות
            action = "HOLD"
            if pl_pct > 20: action = "💰 SELL"
            elif pl_pct < -5 and ai_score > 0.2: action = "♻️ BUY"
            if p_type == "Watchlist" and ai_score > 0.5: action = "🚀 ENTRY"

            final_data.append({
                "Symbol": symbol,
                "Qty": qty,
                "Price": current_price,
                "Value ($)": current_price * qty,
                "Value (₪)": (current_price * qty) * rate,
                "Change %": pl_pct,
                "AI": ai_txt,
                "Action": action,
                "Type": p_type,
                "Date": row['Date']
            })
        except:
            pass # אם יש שגיאה במניה ספציפית, מדלג עליה
            
    return pd.DataFrame(final_data), rate

# ==========================================
# 📱 התצוגה בטלפון
# ==========================================
st.title("My Capital Control")

if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
    with st.spinner("Updating prices & AI..."):
        d, r = load_data()
        st.session_state['df'], st.session_state['rate'] = d, r
        st.rerun()

if 'df' in st.session_state:
    df = st.session_state['df']
    rate = st.session_state['rate']
    
    # חישוב שווי כולל
    total_usd = df['Value ($)'].sum()
    total_ils = total_usd * rate
    
    # כרטיסים למעלה
    c1, c2 = st.columns(2)
    c1.metric("Total (₪)", f"₪{total_ils:,.0f}", f"1$ = {rate:.2f}₪")
    c2.metric("Total ($)", f"${total_usd:,.0f}")
    
    st.markdown("---")
    
    # טבלת נתונים (ה"אקסל" באתר)
    st.subheader("📊 Live Assets")
    
    # עיצוב צבעים לרווח/הפסד
    def color_change(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'white'
        return f'color: {color}'

    # הצגת הטבלה
    view_df = df[['Symbol', 'Date', 'Qty', 'Price', 'Value ($)', 'Change %', 'AI', 'Action']]
    st.dataframe(
        view_df.style.format({
            "Price": "${:.2f}",
            "Value ($)": "${:,.0f}",
            "Change %": "{:.2f}%"
        }).applymap(color_change, subset=['Change %']),
        use_container_width=True,
        height=500
    )
    
else:
    st.info("👆 Click REFRESH to load portfolio")
