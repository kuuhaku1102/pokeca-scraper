import time
import os
import base64
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 🔐 認証ファイルを環境変数から生成
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# 📄 Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit").worksheet("dash")

# 🌐 Chrome起動（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 🔄 oripa-dash ページ読み込み＋スクロール
print("🔍 oripa-dash.com を読み込み中...")
driver.get("https://oripa-dash.com/user/packList")
time.sleep(2)

last_height = driver.execute_script("return document.body.scrollHeight")
scroll_attempts = 0
while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        scroll_attempts += 1
        if scroll_attempts >= 3:
            break
    else:
        scroll_attempts = 0
    last_height = new_height

# 🔍 HTML取得 & パース
soup = BeautifulSoup(driver.page_source, "html.parser")
items = soup.select(".packList__item")

# 📦 データ収集（タイトル・画像URL・詳細URL）
result = [["タイトル", "画像URL", "URL"]]
for item in items:
    title = item.get("data-pack-name", "No Title").strip()
    pack_id = item.get("data-pack-id", "").strip()
    url = f"https://oripa-dash.com/user/packDetail/{pack_id}" if pack_id else ""

    img_tag = item.select_one("img.packList__item-thumbnail")
    img_url = img_tag.get("src") if img_tag else ""
    if img_url.startswith("/"):
        img_url = "https://oripa-dash.com" + img_url

    result.append([title, img_url, url])

print(f"🟢 取得件数: {len(result)-1} 件")

# 📤 スプレッドシートに保存
sheet.clear()
sheet.append_rows(result)
print("✅ Google Sheetsに保存完了")

# 終了処理
driver.quit()
