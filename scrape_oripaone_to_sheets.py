import os
import base64
import time
import gspread
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from google.oauth2.service_account import Credentials
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# credentials.json を出力
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode())

# Google Sheets 認証
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")

# Selenium セットアップ
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("🔍 oripaone スクレイピング開始...")
driver.get("https://oripaone.jp/")
time.sleep(3)  # JS描画待ち

soup = BeautifulSoup(driver.page_source, "html.parser")
cards = soup.select("div.shadow > a[href^='/packs/']")

data = []
for a_tag in cards:
    href = a_tag["href"]
    full_url = "https://oripaone.jp" + href
    img_tag = a_tag.find("img")
    if img_tag:
        img_url = img_tag.get("src")
        title = img_tag.get("alt", "").strip() or os.path.basename(href)
        data.append([title, img_url, full_url])

driver.quit()

print(f"✅ 取得件数: {len(data)} 件")

# スプレッドシート出力
sheet.clear()
sheet.update(values=[["タイトル", "画像URL", "URL"]], range_name="A1")
if data:
    sheet.update(values=data, range_name="A2")
