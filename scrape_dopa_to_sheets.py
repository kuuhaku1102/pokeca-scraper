from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import base64
import os
import gspread
from google.oauth2.service_account import Credentials

# 認証ファイルを作成
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

# Google Sheets 接続
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("dopa")  # ← dopaシートに変更

# 既存の画像URLリストを取得（2行目以降のB列）
existing_data = sheet.get_all_values()[1:]  # ヘッダーを除外
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

# Chrome options
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,2000")
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Chrome 起動
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("🔍 dopa スクレイピング開始...")
driver.get("https://dopa-game.jp/")

try:
    # 少なくとも5件の画像が表示されるまで待つ
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, 'img[src*="/uploads/"]')) >= 5
    )
except:
    print("❌ 要素が読み込まれませんでした。")
    driver.quit()
    exit()

# HTML取得とパース
soup = BeautifulSoup(driver.page_source, "html.parser")
cards = soup.select('a[href*="itemDetail"]')

results = []
for card in cards:
    img_tag = card.find("img")

    if card and img_tag:
        title = img_tag.get("alt") or "無題"
        image_url = img_tag.get("src")
        detail_url = card["href"]

        if image_url.startswith("/"):
            image_url = "https://dopa-game.jp" + image_url
        if detail_url.startswith("/"):
            detail_url = "https://dopa-game.jp" + detail_url

        # スキップ判定：既存画像URLと一致していたらスキップ
        if image_url in existing_image_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        results.append([title, image_url, detail_url])

driver.quit()
print(f"✅ 取得件数（新規のみ）: {len(results)} 件")

# 追記
if results:
    next_row = len(existing_data) + 2  # 1行目がヘッダーなので +2
    sheet.update(f"A{next_row}", results)
