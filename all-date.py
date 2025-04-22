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

# credentials.json を再構築
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

# Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
ws = sheet.worksheet("シート2")

# URL一覧取得（A列）
urls = ws.col_values(1)[1:]

# Chrome起動設定（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# データ書き込み（B列以降）
ws.update("B2:D2", [["カード名", "画像URL", "直近価格JSON"]])

for i, url in enumerate(urls, start=2):
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # カード名取得
    card_name = soup.find("h1", class_="entry-title")
    card_name = card_name.text.strip() if card_name else ""

    # 画像URL取得
    img_tag = soup.select_one("figure.eye-catch img")
    img_url = img_tag["src"] if img_tag else ""

    # 価格情報取得
    price_table = soup.find("tbody", id="item-price-table")
    prices = {"美品": "", "キズあり": "", "PSA10": ""}
    if price_table:
        rows = price_table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if cells and "直近価格" in cells[0].text:
                prices["美品"] = cells[1].text.strip() if len(cells) > 1 else ""
                prices["キズあり"] = cells[2].text.strip() if len(cells) > 2 else ""
                prices["PSA10"] = cells[3].text.strip() if len(cells) > 3 else ""

    price_json = json.dumps(prices, ensure_ascii=False)
    ws.update(f"B{i}:D{i}", [[card_name, img_url, price_json]])

driver.quit()
