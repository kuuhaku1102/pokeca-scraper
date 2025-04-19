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

# 認証ファイル生成
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# Google Sheets認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit").worksheet("シート1")
urls = sheet.col_values(3)[1:]  # C列URL

# Chrome起動（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 現在の行数とカード名一覧取得
existing_card_names = sheet.col_values(1)
current_rows = len(existing_card_names)
next_row = current_rows + 1

# 上限チェック
if current_rows >= 1000:
    print("✅ 1000行を超えたため上書きリセットします")
    sheet.clear()
    sheet.update(range_name='A1', values=[["カード名", "画像", "URL", "直近価格JSON"]])
    existing_card_names = []
    next_row = 2

for url in urls:
    if not url.startswith("http"):
        continue

    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table = soup.find("tbody", id="item-price-table")
    prices = {"美品": "", "キズあり": "", "PSA10": ""}

    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            tds = rows[1].find_all("td")
            if len(tds) >= 4:
                prices["美品"] = tds[1].text.strip()
                prices["キズあり"] = tds[2].text.strip()
                prices["PSA10"] = tds[3].text.strip()

    card_name = soup.find("h1").text.strip() if soup.find("h1") else ""
    img_tag = soup.find("img")
    img_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
    full_img_url = img_url if img_url.startswith("http") else "https://pokeca-chart.com" + img_url

    # カード名が存在すればその行に上書き、なければ追記
    if card_name in existing_card_names:
        row_index = existing_card_names.index(card_name) + 1
        sheet.update(f'A{row_index}:D{row_index}', [[card_name, full_img_url, url, json.dumps(prices, ensure_ascii=False)]])
    else:
        sheet.update(f'A{next_row}:D{next_row}', [[card_name, full_img_url, url, json.dumps(prices, ensure_ascii=False)]])
        next_row += 1
        existing_card_names.append(card_name)

driver.quit()
