import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import os
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import schedule
import time
import warnings
from datetime import datetime
import google.generativeai as genai

warnings.filterwarnings("ignore")

# ==========================================
# 🔑 הגדרות משתמש (מלא את הפרטים שלך)
# ==========================================
EMAIL_SENDER = "medayan3@gmail.com"         # המייל שלך
EMAIL_PASSWORD = "xzkv vnrv nxbd zrza"      # הסיסמה החדשה שיצרת (אם החלפת)
EMAIL_RECEIVER = "medayan3@gmail.com"

GEMINI_API_KEY = "AIzaSyAg2eBXEQMWbrjX3QIqFuLWl7xHkSfC2j0"      # <--- מחק את הטקסט והדבק את המפתח שהעתקת עכשיו

# הגדרת ה-AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"⚠️ API Key Error: {e}")

EXCEL_CONFIG_FILE = "my_stock_config.xlsx"
WORKSPACE_DIR = "Portfolio_Reports"

# ==========================================
# 🧠 פונקציית ה-AI (המוח החדש)
# ==========================================
def analyze_news_with_ai(ticker, news_list):
    if not news_list: return "No meaningful news found.", 0
    
    # איסוף 3 הכותרות האחרונות
    headlines = [n.get('title', '') for n in news_list[:3]]
    headlines_text = ". ".join(headlines)
    
    # ההנחיה ל-AI
    prompt = f"""
    You are a financial analyst. Analyze these headlines for {ticker}:
    "{headlines_text}"
    
    1. Summarize the main event in ONE short sentence.
    2. Provide a sentiment score between -1 (Negative) and 1 (Positive).
    
    Output format: Summary | Score
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "|" in text:
            summary, score = text.split("|")
            return summary.strip(), float(score)
        else:
            return text.replace("\n", " "), 0
    except Exception as e:
        return "AI Analysis Unavailable", 0

# ==========================================
# 📧 פונקציות מייל
# ==========================================
def send_html_email(subject, html_body, attachment_path):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        if os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(attachment_path)}")
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print("📧 AI Report Email Sent Successfully!")
    except Exception as e:
        print(f"❌ Email Failed: {e}")

# ==========================================
# 🚀 המנוע הראשי
# ==========================================
def run_robot():
    print(f"\n🤖 AI ROBOT STARTED: {datetime.now().strftime('%H:%M:%S')}")
    
    # טעינת נתונים מהאקסל שיצרנו קודם
    # אנו מחפשים את הקובץ גם בתיקייה הנוכחית וגם בתיקייה ראשית למקרה של טעות במיקום
    possible_paths = [EXCEL_CONFIG_FILE, f"../{EXCEL_CONFIG_FILE}", f"c:/bot/{EXCEL_CONFIG_FILE}"]
    config_path = None
    
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            break
            
    if not config_path:
        print(f"❌ Error: '{EXCEL_CONFIG_FILE}' not found! Please run create_excel.py first.")
        return

    config_df = pd.read_excel(config_path)
    print(f"✅ Loaded portfolio from {config_path}")
    
    if os.path.exists(WORKSPACE_DIR): shutil.rmtree(WORKSPACE_DIR)
    os.makedirs(f"{WORKSPACE_DIR}/Charts")
    
    report_data = []
    total_invested = 0
    total_value = 0
    html_rows = ""

    print("📊 Fetching data & Analyzing with AI...")
    
    for index, row in config_df.iterrows():
        ticker = row['Symbol']
        stock_type = row['Type'] # Holdings / Watchlist
        
        try:
            print(f"   Analyzing {ticker}...", end="\r")
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y")
            
            if df.empty: continue
            
            current_price = df['Close'].iloc[-1]
            
            # AI Check
            ai_summary, ai_score = analyze_news_with_ai(ticker, stock.news)
            
            # חישובים
            pl_percent = 0
            action = "WATCH"
            bg_color = "#ffffff"
            
            if stock_type == 'Holdings':
                buy_price = row['Buy_Price']
                qty = row['Qty']
                invested = buy_price * qty
                curr_val = current_price * qty
                
                total_invested += invested
                total_value += curr_val
                pl_percent = ((current_price - buy_price) / buy_price) * 100
                
                # החלטות
                if pl_percent > 15: action = "💰 TAKE PROFIT"
                elif pl_percent < -5 and ai_score > 0: action = "♻️ BUY DIP (Good News)"
                else: action = "HOLD"
                
                bg_color = "#e6ffe6" if pl_percent > 0 else "#ffe6e6"

            else: # Watchlist
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                if not pd.isna(df['SMA50'].iloc[-1]) and df['SMA50'].iloc[-1] > df['SMA200'].iloc[-1]:
                    action = "🚀 UPTREND ENTRY"
                
                if ai_score > 0.7: 
                    action = "🔥 HOT NEWS"
                    bg_color = "#ffffcc"

            # הוספה לטבלה
            html_rows += f"""
            <tr style="background-color: {bg_color};">
                <td><b>{ticker}</b></td>
                <td>${current_price:.2f}</td>
                <td>{pl_percent:.2f}%</td>
                <td>{ai_summary}</td>
                <td><b>{action}</b></td>
            </tr>
            """
            
            report_data.append({
                "Symbol": ticker, "Type": stock_type, "Price": current_price,
                "P/L %": pl_percent, "AI Summary": ai_summary, "Action": action
            })
            
        except Exception as e: print(f"Error {ticker}: {e}")

    print("\n💾 Saving report...")
    res_df = pd.DataFrame(report_data)
    res_path = f"{WORKSPACE_DIR}/AI_Analysis_Report.xlsx"
    res_df.to_excel(res_path, index=False)
    
    total_pl = total_value - total_invested
    
    html_body = f"""
    <h2>🤖 AI Market Intelligence Report</h2>
    <p><b>Total P/L:</b> <span style="color: {'green' if total_pl>0 else 'red'}">${total_pl:.0f}</span></p>
    <table border="1" style="border-collapse: collapse; width: 100%; font-family: Arial;">
        <tr style="background-color: #333; color: white;"><th>Stock</th><th>Price</th><th>P/L %</th><th>AI Insight 🧠</th><th>Action</th></tr>
        {html_rows}
    </table>
    <p><i>Generated by your Python AI Robot</i></p>
    """
    
    send_html_email(f"AI Stock Report: P/L ${total_pl:.0f}", html_body, res_path)
    print("✅ Done.")

# הרצה מיידית
run_robot()

# תזמון
print("⏰ Scheduler Active (Running daily at 16:00 & 23:30)...")
schedule.every().day.at("16:00").do(run_robot)
schedule.every().day.at("23:30").do(run_robot)

while True:
    schedule.run_pending()
    time.sleep(60)