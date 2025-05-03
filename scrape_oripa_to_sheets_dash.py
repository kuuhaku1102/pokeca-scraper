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
from google.oauth2.service_account import Credentials

# ======== 認証ファイル保存 ========
CREDENTIALS_FILE = "credentials.json"
encoded_json = os.environ.get("GSHEET_JSON", "")
if not encoded_json:
    raise Exception("❌ GSHEET_JSON が空です。base64文字列を GitHub Secrets に登録してください。")

with open(CREDENTIALS_FILE, "wb") as f:
    f.write(base64.b64decode(encoded_json))

# ======== Google Sheets 認証 ========
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit").worksheet("dash")

# ======== Chrome起動（headless） ========
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ======== oripa-dash ページ読み込み＋スクロール ========
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

# ======== HTMLパース & データ抽出 ========
soup = BeautifulSoup(driver.page_source, "html.parser")
items = soup.select(".packList__item")

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

# ======== スプレッドシートに保存 ========
sheet.clear()
sheet.append_rows(result)
print("✅ Google Sheets に保存完了")

driver.quit()
