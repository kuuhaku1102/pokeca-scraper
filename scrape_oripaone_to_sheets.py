import os
import time
import base64
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets 認証設定
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)

# スプレッドシートとシートの指定
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")

# ヘッダーの更新
sheet.update("A1", [["タイトル", "画像URL", "URL"]])

# Seleniumの設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# oripaone.jpのトップページにアクセス
print("🔍 oripaone スクレイピング開始...")
driver.get("https://oripaone.jp/")
time.sleep(5)  # ページの読み込みを待機

# ページソースを取得し、BeautifulSoupで解析
soup = BeautifulSoup(driver.page_source, "html.parser")

# カード要素を取得
cards = soup.find_all("div", class_="relative overflow-hidden rounded bg-white shadow")

results = []
for card in cards:
    a_tag = card.find("a", href=True)
    img_tag = card.find("img")

    if a_tag and img_tag:
        url = "https://oripaone.jp" + a_tag["href"]
        image_url = img_tag.get("src", "")
        title = img_tag.get("alt", "") or "pack"
        results.append([title, image_url, url])

driver.quit()

print(f"✅ 取得件数: {len(results)} 件")

# スプレッドシートに書き込み
if results:
    sheet.update("A2", results)
