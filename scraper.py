import time
import re
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

# ✅ GitHub Secrets から credentials.json を再構築
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# ✅ Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# ✅ スプレッドシートのURLとシート名
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
ws = sheet.worksheet("シート1")

# ✅ URL一覧（C列2行目以降）
urls = ws.col_values(3)[1:]

# ✅ 見出し項目
sections = ["美品", "キズあり", "PSA10"]
labels = ["データ数", "直近価格", "最高価格", "平均価格", "最低価格", "騰落率(7日)", "騰落率(30日)"]
ws.update(range_name='D1', values=[["価格情報JSON"]])

# ✅ Chromeドライバ設定（GitHub Actions対応）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ✅ 各URLに対して価格情報を取得
for i, url in enumerate(urls, start=2):
    if not url.startswith("http"):
        continue
    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table = soup.find("tbody", id="item-price-table")
    data = []

    if table:
        for row in table.find_all("tr"):
            tds = row.find_all("td")
            for td in tds[1:4]:
                val = td.get_text(strip=True)  # ← 修正済み：装飾そのままで取得
                data.append(val)
    else:
        data = [""] * (len(sections) * len(labels))  # 空データ対応

    # カテゴリ別に分割
    b = data[0:7]
    k = data[7:14]
    p = data[14:21]

    # ネスト構造で価格情報を構築
    price_dict = {}
    for idx, label in enumerate(labels):
        price_dict[label] = {
            "美品": b[idx],
            "キズあり": k[idx],
            "PSA10": p[idx]
        }

    # JSONとしてスプレッドシートに保存（1セル）
    ws.update(f'D{i}', [[json.dumps(price_dict, ensure_ascii=False)]])

driver.quit()
