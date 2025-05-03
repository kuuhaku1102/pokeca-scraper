import os
import base64
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# 認証情報をcredentials.jsonに書き出す
CREDENTIALS_FILE = "credentials.json"
with open(CREDENTIALS_FILE, "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode())

# Google Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
gc = gspread.authorize(credentials)

# 対象スプレッドシートとシート
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")

# スクレイピング開始
print("🔍 oripaone スクレイピング開始...")
res = requests.get("https://oripaone.jp/")
soup = BeautifulSoup(res.text, "html.parser")
cards = soup.select("div.shadow > a[href^='/packs/']")

data = []
for card_a in cards:
    link = card_a.get("href")
    full_url = "https://oripaone.jp" + link
    img_tag = card_a.find("img")
    if not img_tag:
        continue
    img_url = img_tag.get("src")
    title = img_tag.get("alt", "").strip()
    if not title:
        title = os.path.basename(link)  # 代替
    data.append([title, img_url, full_url])

print(f"✅ 取得件数: {len(data)} 件")

# スプレッドシートに書き込み
sheet.clear()
sheet.update("A1", [["タイトル", "画像URL", "URL"]])
if data:
    sheet.update("A2", data)
