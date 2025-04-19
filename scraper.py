import time
import re
import os
import base64
import json
import pymysql
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ✅ GitHub Secrets から credentials.json を復元
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
headers = [f"{s}_{l}" for s in sections for l in labels]
ws.update(range_name='D1', values=[headers])

# ✅ Seleniumでページ取得
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

results = []

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
            for td in tds[1:4]:  # 美品, キズあり, PSA10
                val = td.get_text(strip=True).replace(",", "").replace("円", "").replace("%", "").replace("(", "").replace(")", "")
                data.append(val)
    else:
        data = [""] * len(headers)

    ws.update(f'D{i}', [data])

    # ✅ MySQL保存用のデータをまとめる
    results.append({
        "カード名": ws.cell(i, 1).value,  # A列：カード名
        "画像": "",                      # 画像がない場合は空にしておく
        "URL": url,
        "美品_データ数": data[0], "美品_直近価格": data[1], "美品_最高価格": data[2], "美品_平均価格": data[3],
        "美品_最低価格": data[4], "美品_騰落率(7日)": data[5], "美品_騰落率(30日)": data[6],
        "キズあり_データ数": data[7], "キズあり_直近価格": data[8], "キズあり_最高価格": data[9], "キズあり_平均価格": data[10],
        "キズあり_最低価格": data[11], "キズあり_騰落率(7日)": data[12], "キズあり_騰落率(30日)": data[13],
        "PSA10_データ数": data[14], "PSA10_直近価格": data[15], "PSA10_最高価格": data[16], "PSA10_平均価格": data[17],
        "PSA10_最低価格": data[18], "PSA10_騰落率(7日)": data[19], "PSA10_騰落率(30日)": data[20]
    })

driver.quit()

# ✅ MySQL に保存
conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    charset='utf8mb4'
)
cursor = conn.cursor()

for card in results:
    sql = """
    INSERT INTO wp_pokeca_prices (
      card_title, image_url, card_url,
      price_b, price_k, price_p
    ) VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (
        card["カード名"],
        card["画像"],
        card["URL"],
        json.dumps({
            "データ数": card["美品_データ数"],
            "直近価格": card["美品_直近価格"],
            "最高価格": card["美品_最高価格"],
            "平均価格": card["美品_平均価格"],
            "最低価格": card["美品_最低価格"],
            "騰落率(7日)": card["美品_騰落率(7日)"],
            "騰落率(30日)": card["美品_騰落率(30日)"]
        }, ensure_ascii=False),
        json.dumps({
            "データ数": card["キズあり_データ数"],
            "直近価格": card["キズあり_直近価格"],
            "最高価格": card["キズあり_最高価格"],
            "平均価格": card["キズあり_平均価格"],
            "最低価格": card["キズあり_最低価格"],
            "騰落率(7日)": card["キズあり_騰落率(7日)"],
            "騰落率(30日)": card["キズあり_騰落率(30日)"]
        }, ensure_ascii=False),
        json.dumps({
            "データ数": card["PSA10_データ数"],
            "直近価格": card["PSA10_直近価格"],
            "最高価格": card["PSA10_最高価格"],
            "平均価格": card["PSA10_平均価格"],
            "最低価格": card["PSA10_最低価格"],
            "騰落率(7日)": card["PSA10_騰落率(7日)"],
            "騰落率(30日)": card["PSA10_騰落率(30日)"]
        }, ensure_ascii=False),
    ))

conn.commit()
cursor.close()
conn.close()

print("✅ スプレッドシート & MySQLへの保存完了！")
