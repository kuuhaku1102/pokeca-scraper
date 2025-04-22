import time
import os
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# credentials.json を再構築
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
ws = sheet.worksheet("シート2")

# Chrome起動設定（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# pokeca-chart all-cardページにアクセスしてスクロール（1000件以上を目指す）
url = "https://pokeca-chart.com/all-card?mode=1"
driver.get(url)
time.sleep(2)

# スクロールを多めに（例：40回）
from selenium.webdriver.common.by import By

MAX_SCROLLS = 1000
last_height = driver.execute_script("return document.body.scrollHeight")
scroll_attempts = 0
no_change_count = 0
previous_count = 0

for scroll_index in range(MAX_SCROLLS):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)  # スクロール直後の遅延に対応

    # 新しいカードが読み込まれたかを確認
    cards = driver.find_elements(By.CLASS_NAME, "cp_card")
    current_count = len(cards)

    if current_count == previous_count:
        no_change_count += 1
        if no_change_count >= 5:  # ←連続して変化がなければ終了
            print("✅ スクロール終了条件に達しました")
            break
    else:
        no_change_count = 0

    previous_count = current_count

    print(f"🔁 スクロール {scroll_index+1} 回目: 現在 {current_count} 件")

# HTML取得・パース
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")
cards = soup.find_all("div", class_="cp_card")

# URL一覧抽出
card_urls = []
for card in cards:
    a_tag = card.find("a", href=True)
    if a_tag and a_tag["href"].startswith("https://pokeca-chart.com/s"):
        card_urls.append([a_tag["href"]])

print(f"✅ 取得URL数: {len(card_urls)} 件")

# スプレッドシートのシート2へ出力
# スプレッドシートのシート2へ出力（ヘッダー行を保持）
num_rows = len(ws.col_values(1))
if num_rows > 1:
    ws.batch_clear([f"A2:A{num_rows}"])  # 2行目以降をクリア

# ヘッダーがない場合のみ挿入（例外対策）
if not ws.cell(1, 1).value:
    ws.update("A1", [["カード詳細URL"]])

# データをA2から出力
if card_urls:
    ws.update(f"A2:A{len(card_urls)+1}", card_urls)

driver.quit()
