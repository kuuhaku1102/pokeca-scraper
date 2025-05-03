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

# 環境変数から認証情報を書き出し
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

# Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gc = gspread.authorize(creds)

# スプレッドシートとシート名指定
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")

# Chrome headless オプション
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# oripaone トップページ取得
print("🔍 oripaone スクレイピング開始...")
driver.get("https://oripaone.jp/")
time.sleep(3)
soup = BeautifulSoup(driver.page_source, "html.parser")

# カード一覧ブロック抽出（クラス構成が動的なため shadow などの一部で検出）
cards = soup.find_all("div", attrs={"class": lambda x: x and "shadow" in x and "overflow-hidden" in x})

results = []
for card in cards:
    a_tag = card.find("a", href=True)
    img_tag = card.find("img")

    if a_tag and img_tag:
        url = "https://oripaone.jp" + a_tag["href"]
        image_url = img_tag.get("src", "")
        title = img_tag.get("alt", "") or "pack"
        results.append([title, image_url, url])

# スプレッドシートに出力
if results:
    sheet.clear()
    sheet.update(values=[["タイトル", "画像URL", "URL"]])
    sheet.update(values=results, range_name=f"A2")
print(f"✅ 取得件数: {len(results)} 件")

driver.quit()
