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

# 既存のURL一覧を取得（1行目は見出しなので除外）
existing_urls = ws.col_values(1)[1:]
existing_urls_set = set(existing_urls)

# Chrome起動設定（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# pokeca-chart all-cardページにアクセスしてスクロール
url = "https://pokeca-chart.com/all-card?mode=1"
driver.get(url)
time.sleep(2)

# ページの一番下までスクロール
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

# HTML取得・パース
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")
cards = soup.find_all("div", class_="cp_card")

# 新規URL抽出（既存と重複しないものだけ）
new_urls = []
for card in cards:
    a_tag = card.find("a", href=True)
    if a_tag and a_tag["href"].startswith("https://pokeca-chart.com/s"):
        url = a_tag["href"]
        if url not in existing_urls_set:
            new_urls.append([url])

print(f"✅ 新規取得URL数: {len(new_urls)} 件")

# スプレッドシートへ追記
if new_urls:
    start_row = len(existing_urls) + 2  # 見出し行+既存データ+1
    ws.update(f"A{start_row}:A{start_row + len(new_urls) - 1}", new_urls)
    print(f"✅ スプレッドシートに {len(new_urls)} 件追記しました")
else:
    print("⚠️ 新規URLはありませんでした（すべて既出）")

driver.quit()
