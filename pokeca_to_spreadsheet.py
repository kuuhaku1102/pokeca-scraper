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

# ✅ Google Sheets認証
with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit").worksheet("シート1")

# ✅ Chrome起動設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ✅ pokeca-chart.com/all-card?mode=1 を読み込み・スクロール
driver.get("https://pokeca-chart.com/all-card?mode=1")
last_height = driver.execute_script("return document.body.scrollHeight")
scroll_attempts = 0
max_scrolls = 15  # 調整可能

for _ in range(max_scrolls):
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

# ✅ URL取得
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")
cards = soup.find_all("div", class_="cp_card04")
card_urls = []
for card in cards:
    a_tag = card.find("a", href=True)
    if a_tag and a_tag["href"].startswith("https://pokeca-chart.com/s"):
        card_urls.append(a_tag["href"])
card_urls = list(set(card_urls))
print(f"✅ 取得件数: {len(card_urls)}")

# ✅ スプレッドシート初期化条件
existing_card_names = sheet.col_values(1)
if len(existing_card_names) >= 1000:
    sheet.clear()
    sheet.update(range_name='A1', values=[["カード名", "画像", "URL", "直近価格JSON"]])
    existing_card_names = []
    next_row = 2
else:
    next_row = len(existing_card_names) + 1

# ✅ 詳細情報を取得しながらシートに書き込み
for url in card_urls:
    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    prices = {"美品": "", "キズあり": "", "PSA10": ""}
    table = soup.find("tbody", id="item-price-table")
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

    if card_name in existing_card_names:
        row_index = existing_card_names.index(card_name) + 1
        sheet.update(f'A{row_index}:D{row_index}', [[card_name, full_img_url, url, json.dumps(prices, ensure_ascii=False)]])
    else:
        sheet.update(f'A{next_row}:D{next_row}', [[card_name, full_img_url, url, json.dumps(prices, ensure_ascii=False)]])
        next_row += 1
        existing_card_names.append(card_name)

driver.quit()
