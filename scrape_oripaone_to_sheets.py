import os
import time
import base64
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets認証
CREDENTIALS_FILE = "credentials.json"
with open(CREDENTIALS_FILE, "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode())

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
gc = gspread.authorize(credentials)

# スプレッドシートとシート名
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")

# スクレイピング処理
print("🔍 oripaone スクレイピング開始...")
res = requests.get("https://oripaone.jp/")
soup = BeautifulSoup(res.text, "html.parser")
cards = soup.select("div.relative.shadow a[href^='/packs/'] img")

data = []
for card in cards:
    img_url = card.get("src")
    if img_url:
        data.append([img_url])

print(f"✅ 取得件数: {len(data)} 件")

# シートクリア＆ヘッダー書き込み＆データ書き込み
sheet.clear()
sheet.update("A1", [["画像URL"]])
if data:
    sheet.update("A2", data)
