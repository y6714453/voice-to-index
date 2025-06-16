import json
import yfinance as yf
import asyncio
import datetime
import os
import subprocess
from edge_tts import Communicate
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests
import pandas as pd

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"
UPLOAD_PATH = "ivr2:/1/1/1/99"
FFMPEG_PATH = "./bin/ffmpeg"

# טוען את רשימת המניות מהקובץ CSV
def load_stock_list(csv_path):
    df = pd.read_csv(csv_path)
    stock_dict = {}
    for _, row in df.iterrows():
        stock_dict[row['search_name'].strip()] = {
            "ticker": row['ticker'].strip(),
            "type": row['type'].strip(),
            "speak_name": row['speak_name'].strip()
        }
    return stock_dict

# המרת מספרים לטקסט בעברית (פשוטה)
def number_to_words(num):
    return str(round(num, 2)).replace('.', ' נקודה ')

# יוצר טקסט הקראה עבור מניה או מדד
def generate_text(name, data, speak_name):
    change_daily = data['regularMarketChangePercent']
    change_weekly = ((data['regularMarketPrice'] - data['fiftyTwoWeekLow']) / data['fiftyTwoWeekLow']) * 100
    change_monthly = ((data['regularMarketPrice'] - data['fiftyDayAverage']) / data['fiftyDayAverage']) * 100
    change_yearly = ((data['regularMarketPrice'] - data['fiftyTwoWeekLow']) / data['fiftyTwoWeekLow']) * 100
    distance_from_high = ((data['fiftyTwoWeekHigh'] - data['regularMarketPrice']) / data['fiftyTwoWeekHigh']) * 100

    direction = lambda x: "עלייה" if x > 0 else "ירידה" if x < 0 else "ללא שינוי"
    percent = lambda x: f"{abs(round(x, 2))} אחוז"

    return f"""
{name} – {direction(change_daily)} של {percent(change_daily)} היום,
{direction(change_weekly)} של {percent(change_weekly)} בשבוע האחרון,
{direction(change_monthly)} של {percent(change_monthly)} בחודש האחרון,
{direction(change_yearly)} של {percent(change_yearly)} בשנה האחרונה.
המחיר הנוכחי רחוק מהשיא ב־{percent(distance_from_high)}.
"""

# יצירת קובץ MP3 באמצעות Edge-TTS
async def create_mp3(text, output_path):
    communicate = Communicate(text, voice="he-IL-HilaNeural", rate="-20%")
    await communicate.save(output_path)

# המרת MP3 ל-WAV
def convert_to_wav(mp3_path, wav_path):
    subprocess.run([FFMPEG_PATH, "-y", "-i", mp3_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# העלאת קובץ לימות המשיח
def upload_to_yemot(wav_path):
    with open(wav_path, 'rb') as f:
        m = MultipartEncoder(fields={"file": ("file", f, "audio/wav")})
        res = requests.post(
            f"https://www.call2all.co.il/ym/api/UploadFile?token={TOKEN}&path={UPLOAD_PATH}",
            data=m,
            headers={"Content-Type": m.content_type}
        )
        print("סטטוס העלאה:", res.status_code, res.text)

# פונקציית הריצה הראשית
async def main_loop():
    stock_dict = load_stock_list("hebrew_stocks.csv")
    for search_name, info in stock_dict.items():
        ticker = info["ticker"]
        speak_name = info["speak_name"]
        try:
            stock = yf.Ticker(ticker)
            data = stock.info
            text = generate_text(speak_name, data, speak_name)
            print("📢", text)
            await create_mp3(text, "temp.mp3")
            convert_to_wav("temp.mp3", "output.wav")
            upload_to_yemot("output.wav")
            break  # מספק להריץ פעם אחת לבדיקה
        except Exception as e:
            print(f"שגיאה בנתונים עבור {search_name}: {e}")

# הפעלת הלולאה
if __name__ == "__main__":
    asyncio.run(main_loop())
