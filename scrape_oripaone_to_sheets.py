import os
import time
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 認証ファイルを保存
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# Google Sheets認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# スプレッドシートを開く
sheet = client.open("oripaone").sheet1

# Seleniumセットアップ
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# URLを開く
driver.get("https://oripaone.jp/")
time.sleep(3)

# HTML解析
soup = BeautifulSoup(driver.page_source, "html.parser")
driver.quit()

# 画像URLの取得
image_urls = []
for img in soup.select("div.grid a img"):
    src = img.get("src")
    if src:
        if src.startswith("/"):
            src = "https://oripaone.jp" + src
        image_urls.append(src)

# 重複排除
image_urls = list(set(image_urls))

# スプレッドシートにヘッダーがなければ追加
if not sheet.row_values(1):
    sheet.append_row(["画像URL"])

# 書き込み（1件ずつ）
for url in image_urls:
    sheet.append_row([url])
