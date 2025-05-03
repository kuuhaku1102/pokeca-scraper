import os
import time
import base64
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets 認証
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("oripaone")
sheet.update(values=[["タイトル", "画像URL", "URL"]], range_name="A1")

# Selenium 起動
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("🔍 oripaone スクレイピング開始...")
driver.get("https://oripaone.jp/")

# div.relative ... を最大10秒待機（JSで読み込み完了まで）
try:
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.relative.overflow-hidden.rounded.bg-white.shadow"))
    )
except:
    print("❌ 要素が読み込まれませんでした。")
    driver.quit()
    exit()

soup = BeautifulSoup(driver.page_source, "html.parser")
cards = soup.select("div.relative.overflow-hidden.rounded.bg-white.shadow")

results = []
for card in cards:
    a_tag = card.find("a", href=True)
    img_tag = card.find("img")

    if a_tag and img_tag:
        title = img_tag.get("alt", "") or "pack"
        image_url = img_tag.get("src", "")
        detail_url = "https://oripaone.jp" + a_tag["href"]
        results.append([title, image_url, detail_url])

driver.quit()
print(f"✅ 取得件数: {len(results)} 件")

if results:
    sheet.update(values=results, range_name="A2")
