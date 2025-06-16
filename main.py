import os
import asyncio
import pandas as pd
import yfinance as yf
import subprocess
from edge_tts import Communicate
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"
UPLOAD_PATH = "ivr2:/99/001.wav"
FFMPEG_PATH = "./bin/ffmpeg"

# 🔧 טעינת רשימת ניירות הערך
def load_stock_list(csv_path):
    df = pd.read_csv(csv_path)
    stock_dict = {}
    for _, row in df.iterrows():
        stock_dict[row['search_name'].strip()] = {
            "speak_name": row['speak_name'].strip(),
            "ticker": row['ticker'].strip(),
            "type": row['type'].strip()
        }
    return stock_dict

# 🎯 פונקציה לשליפת נתוני מניה מ־Yahoo Finance
def get_stock_summary(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")
    if hist.empty:
        return None

    last_price = hist['Close'][-1]
    one_day = hist['Close'][-1] / hist['Close'][-2] - 1 if len(hist) > 1 else 0
    one_week = hist['Close'][-1] / hist['Close'][-6] - 1 if len(hist) > 5 else 0
    one_month = hist['Close'][-1] / hist['Close'][-21] - 1 if len(hist) > 20 else 0
    one_year = hist['Close'][-1] / hist['Close'][0] - 1 if len(hist) > 60 else 0
    peak = hist['Close'].max()
    from_peak = (last_price - peak) / peak

    return {
        "price": last_price,
        "change_day": one_day,
        "change_week": one_week,
        "change_month": one_month,
        "change_year": one_year,
        "from_peak": from_peak
    }

# 🎙️ יצירת טקסט לקריינות
def generate_text(name, data):
    def fmt(pct):
        sign = "עלייה" if pct > 0 else "ירידה" if pct < 0 else "שינוי"
        return f"{sign} של {abs(pct * 100):.1f} אחוז"

    price_str = f"שער אחרון של {data['price']:.2f} דולר"
    return (
        f"{name}: {fmt(data['change_day'])} היום, "
        f"{fmt(data['change_week'])} בשבוע האחרון, "
        f"{fmt(data['change_month'])} בחודש האחרון, "
        f"{fmt(data['change_year'])} בשלושת החודשים, "
        f"{price_str}. "
        f"המחיר הנוכחי רחוק מהשיא ב{abs(data['from_peak'] * 100):.1f} אחוז."
    )

# 🗣️ יצירת קריינות עם Edge-TTS
async def text_to_speech(text, mp3_path):
    communicate = Communicate(text, voice="he-IL-AvriNeural", rate="-20%")
    await communicate.save(mp3_path)

# 🔄 המרת MP3 ל-WAV
def convert_to_wav(mp3_path, wav_path):
    subprocess.run([
        FFMPEG_PATH, "-y",
        "-i", mp3_path,
        "-ar", "8000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        wav_path
    ])

# ☁️ העלאת הקובץ לימות המשיח
def upload_to_yemot(wav_path):
    with open(wav_path, 'rb') as f:
        m = MultipartEncoder(fields={
            'token': TOKEN,
            'path': UPLOAD_PATH,
            'file': ('file', f, 'audio/wav')
        })
        response = requests.post("https://www.call2all.co.il/ym/api/UploadFile", data=m, headers={'Content-Type': m.content_type})
        return response.text

# 🚀 הפעלת הכל
async def main_loop():
    stock_dict = load_stock_list("stocks_hebrew.csv")
    user_input = input("📥 הקלד שם נייר ערך בעברית: ").strip()

    if user_input not in stock_dict:
        print("❌ שם נייר הערך לא נמצא ברשימה.")
        return

    item = stock_dict[user_input]
    print(f"🔍 מוצא נתונים עבור {item['speak_name']} ({item['ticker']})...")

    data = get_stock_summary(item["ticker"])
    if data is None:
        print("⚠️ לא נמצאו נתונים עבור הטיקר.")
        return

    text = generate_text(item["speak_name"], data)
    print(f"📄 טקסט להקראה:\n{text}")

    await text_to_speech(text, "output.mp3")
    convert_to_wav("output.mp3", "output.wav")
    result = upload_to_yemot("output.wav")
    print(f"✅ הסתיים. תשובת ימות המשיח: {result}")

if __name__ == "__main__":
    asyncio.run(main_loop())
