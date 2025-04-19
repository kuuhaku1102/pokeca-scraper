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

# ヘッダーセット
sheet.update(range_name='D1', values=[["直近価格JSON"]])

# Chrome起動（headless）
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

for i, url in enumerate(urls, start=2):
    if not url.startswith("http"):
        continue

    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table = soup.find("tbody", id="item-price-table")
    prices = {"美品": "", "キズあり": "", "PSA10": ""}

    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:  # 「直近価格」は2番目の行
            tds = rows[1].find_all("td")
            if len(tds) >= 4:
                prices["美品"] = tds[1].text.strip()
                prices["キズあり"] = tds[2].text.strip()
                prices["PSA10"] = tds[3].text.strip()

    sheet.update(f'D{i}', [[json.dumps(prices, ensure_ascii=False)]])

driver.quit()
