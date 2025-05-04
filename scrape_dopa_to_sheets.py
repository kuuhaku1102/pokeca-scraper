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

# --- Google Sheets 認証 ---
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("dopa")

# --- ヘッダー整備 ---
expected_header = ["タイトル", "画像URL", "URL"]
current_header = sheet.row_values(1)
if current_header != expected_header:
    sheet.update("A1", [expected_header])

# --- 既存データ取得（重複判定用） ---
existing_data = sheet.get_all_values()[1:]  # ヘッダーを除く
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

# --- Selenium設定 ---
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,2000")
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- スクレイピング開始 ---
print("🔍 dopa-game.jp スクレイピング開始...")
driver.get("https://dopa-game.jp/")

try:
    # ガチャ画像が複数読み込まれるまで待機
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, 'a[href*="itemDetail"] img')) >= 5
    )
except Exception as e:
    print("❌ 要素が十分に読み込まれませんでした。", e)
    driver.quit()
    exit()

# --- HTML取得 & パース ---
soup = BeautifulSoup(driver.page_source, "html.parser")
gacha_blocks = soup.select('a[href*="itemDetail"]')

results = []
for block in gacha_blocks:
    img_tag = block.find("img")
    if not img_tag:
        continue

    title = img_tag.get("alt", "無題").strip()
    image_url = img_tag["src"]
    detail_url = block["href"]

    if image_url.startswith("/"):
        image_url = "https://dopa-game.jp" + image_url
    if detail_url.startswith("/"):
        detail_url = "https://dopa-game.jp" + detail_url

    if image_url in existing_image_urls:
        print(f"⏭ スキップ（重複）: {title}")
        continue

    print(f"✅ 取得: {title}")
    results.append([title, image_url, detail_url])

driver.quit()
print(f"📦 新規取得件数: {len(results)} 件")

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2  # ヘッダー行 +1
    sheet.update(f"A{next_row}", results)
