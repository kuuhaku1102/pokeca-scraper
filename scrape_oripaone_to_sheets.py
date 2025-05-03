# scrape_oripaone_to_sheets.py
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
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets 認証
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gc = gspread.authorize(creds)

sheet = gc.open("oripaone").sheet1

# Chrome起動 (headless)
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("\U0001F50D oripaone スクレイピング開始...")
driver.get("https://oripaone.jp/")
time.sleep(3)
soup = BeautifulSoup(driver.page_source, "html.parser")

cards = soup.select("div.relative.overflow-hidden.rounded.bg-white.shadow")
data = []
for card in cards:
    a_tag = card.find("a", href=True)
    img_tag = card.find("img")
    if a_tag and img_tag:
        detail_url = "https://oripaone.jp" + a_tag["href"]
        img_url = img_tag["src"]
        title = "オリパワン商品"
        data.append([title, img_url, detail_url])

print(f"\u2705 取得件数: {len(data)} 件")

if data:
    sheet.clear()
    sheet.append_row(["タイトル", "画像URL", "URL"])
    for row in data:
        sheet.append_row(row)


# 終了
driver.quit()
