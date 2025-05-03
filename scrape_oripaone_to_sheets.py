import os
import base64
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# 認証ファイル作成
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# スプレッドシート認証と接続
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(credentials)

# 対象スプレッドシートとシート名
SPREADSHEET_ID = "11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE"
SHEET_NAME = "oripaone"
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# スクレイピング対象URL
url = "https://oripaone.jp/"
print("🔍 oripaone スクレイピング開始...")

response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

cards = soup.select("div.relative.rounded.shadow img")
data = []

for card in cards:
    img_url = card.get("src")
    if img_url and img_url.startswith("https://"):
        data.append([img_url])

print(f"✅ 取得件数: {len(data)} 件")

# ヘッダーがなければセット
if sheet.row_count < 1 or sheet.cell(1, 1).value != "画像URL":
    sheet.clear()
    sheet.append_row(["画像URL"])

for row in data:
    sheet.append_row(row)
