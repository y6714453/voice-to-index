import requests
import asyncio
import edge_tts
import os
import subprocess
import speech_recognition as sr
import pandas as pd
import yfinance as yf
from difflib import get_close_matches
from requests_toolbelt.multipart.encoder import MultipartEncoder
import re
import shutil

USERNAME = "0733181201"
PASSWORD = "6714453"
TOKEN = f"{USERNAME}:{PASSWORD}"
DOWNLOAD_PATH = "1/0"  # שלוחת ההקלטות
UPLOAD_PATH = "ivr2:/1/10/001.wav"  # שלוחת הפלט

async def main_loop():
    stock_dict = load_stock_list("hebrew_stocks.csv")
    print("🔁 התחילה לולאה שמזהה קבצים כל שנייה...")

    ensure_ffmpeg()
    last_processed_file = None

    while True:
        filename, file_name_only = download_yemot_file()

        if not file_name_only:
            await asyncio.sleep(1)
            continue

        print("📂 זוהה קובץ...")

        if file_name_only == last_processed_file:
            await asyncio.sleep(1)
            continue

        last_processed_file = file_name_only
        print(f"📥 זוהה קובץ חדש: {file_name_only}")

        if filename:
            recognized = transcribe_audio(filename)
            if recognized:
                best_match = get_best_match(recognized, stock_dict)
                if best_match:
                    stock_info = stock_dict[best_match]
                    data = get_stock_data(stock_info['ticker'])
                    if data:
                        text = f"נמצא מדד בשם {stock_info['display_name']}. המדד עומד על {data['current']} נקודות. מתחילת היום נרשמה {'עלייה' if data['day'] > 0 else 'ירידה'} של {abs(data['day'])} אחוז."
                    else:
                        text = f"לא נמצאו נתונים למדד {stock_info['display_name']}"
                else:
                    text = "לא זוהה נייר ערך תואם"
            else:
                text = "לא זוהה דיבור ברור"

            print(f"🎙️ טקסט להקראה: {text}")
            await create_audio(text, "output.mp3")
            convert_mp3_to_wav("output.mp3", "output.wav")
            upload_to_yemot("output.wav")
            print("✅ סבב הסתיים\n")

        await asyncio.sleep(1)

def ensure_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("⬇️ מתקין ffmpeg...")
        os.makedirs("ffmpeg_bin", exist_ok=True)
        zip_path = "ffmpeg.zip"
        r = requests.get("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
        with open(zip_path, 'wb') as f:
            f.write(r.content)
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("ffmpeg_bin")
        os.remove(zip_path)
        for root, _, files in os.walk("ffmpeg_bin"):
            for file in files:
                if "ffmpeg" in file:
                    os.environ["PATH"] += os.pathsep + os.path.join(root)
                    return
    else:
        print("⏩ ffmpeg כבר קיים")

def download_yemot_file():
    url = "https://www.call2all.co.il/ym/api/GetIVR2Dir"
    params = {"token": TOKEN, "path": DOWNLOAD_PATH}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None, None
    files = response.json().get("files", [])
    valid_files = [(int(f["name"].replace(".wav", "")), f["name"]) for f in files
                   if f.get("exists") and f["name"].endswith(".wav") and not f["name"].startswith("M")]
    if not valid_files:
        return None, None
    _, name = max(valid_files)
    dl_url = "https://www.call2all.co.il/ym/api/DownloadFile"
    dl_params = {"token": TOKEN, "path": f"ivr2:/{DOWNLOAD_PATH}/{name}"}
    r = requests.get(dl_url, params=dl_params)
    if r.status_code == 200:
        with open("input.wav", "wb") as f:
            f.write(r.content)
        return "input.wav", name
    return None, None

def transcribe_audio(filename):
    r = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio, language="he-IL")
    except:
        return ""

def normalize(text):
    return re.sub(r'[^א-תa-zA-Z0-9 ]', '', text).lower().strip()

def load_stock_list(path):
    df = pd.read_csv(path)
    return {
        normalize(row["hebrew_name"]): {
            "display_name": row["display_name"],
            "ticker": row["ticker"],
            "type": row["type"]
        } for _, row in df.iterrows()
    }

def get_best_match(query, stock_dict):
    matches = get_close_matches(normalize(query), stock_dict.keys(), n=1, cutoff=0.6)
    return matches[0] if matches else None

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if len(hist) < 2:
            return None
        current = hist["Close"].iloc[-1]
        day_before = hist["Close"].iloc[-2]
        return {
            "current": round(current, 2),
            "day": round((current - day_before) / day_before * 100, 2)
        }
    except:
        return None

async def create_audio(text, filename="output.mp3"):
    await edge_tts.Communicate(text, voice="he-IL-AvriNeural").save(filename)

def convert_mp3_to_wav(mp3, wav):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3,
                    "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", wav])

def upload_to_yemot(wav_file):
    m = MultipartEncoder(fields={
        "token": TOKEN,
        "path": UPLOAD_PATH,
        "upload": (wav_file, open(wav_file, 'rb'), 'audio/wav')
    })
    r = requests.post("https://www.call2all.co.il/ym/api/UploadFile", data=m,
                      headers={'Content-Type': m.content_type})
    if r.ok:
        print(f"⬆️ הקובץ הועלה לשלוחה {UPLOAD_PATH}")
    else:
        print("❌ שגיאה בהעלאה לימות")

if __name__ == "__main__":
    asyncio.run(main_loop())
