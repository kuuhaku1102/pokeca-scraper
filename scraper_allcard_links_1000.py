import time
import os
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
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

# 既存のURLを取得（A列）
existing_urls = set(ws.col_values(1)[1:])  # A2〜以降

# Chrome設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# mode=1〜20 を全て探索
new_card_urls = []

for mode in range(1, 21):
    url = f"https://pokeca-chart.com/all-card?mode={mode}"
    print(f"▶ モード {mode} のカード取得開始")
    driver.get(url)
    time.sleep(2)

    cards = driver.find_elements(By.CLASS_NAME, "cp_card")
    if len(cards) == 0:
        print(f"❌ モード {mode} は無効またはカードが存在しません。スキップ")
        continue

    # スクロール処理
    last_height = driver.execute_script("return document.body.scrollHeight")
    no_change_count = 0
    previous_count = 0

    for scroll_index in range(1000):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        cards = driver.find_elements(By.CLASS_NAME, "cp_card")
        current_count = len(cards)

        if current_count == previous_count:
            no_change_count += 1
            if no_change_count >= 5:
                print("✅ スクロール終了条件に達しました")
                break
        else:
            no_change_count = 0

        previous_count = current_count
        print(f"🔁 モード {mode} - スクロール {scroll_index+1} 回目: 現在 {current_count} 件")

    # HTMLパース
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="cp_card")

    mode_new_count = 0
    for card in cards:
        a_tag = card.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            if href.startswith("https://pokeca-chart.com/s") and href not in existing_urls:
                new_card_urls.append([href])
                existing_urls.add(href)
                mode_new_count += 1

    print(f"✅ モード {mode} 完了：新規 {mode_new_count} 件")

# スプレッドシート出力（追記のみ）
last_row = len(ws.col_values(1))
start_row = last_row + 1 if last_row else 2

if new_card_urls:
    ws.update(f"A{start_row}:A{start_row + len(new_card_urls) - 1}", new_card_urls)
    print(f"✅ 合計 {len(new_card_urls)} 件の新規URLをスプレッドシートへ追記しました")
else:
    print("⚠ 新規URLはありませんでした")

driver.quit()
