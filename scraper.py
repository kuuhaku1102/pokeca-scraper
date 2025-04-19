import base64, os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials  # ← これ！
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pymysql
import json


with open("credentials.json", "wb") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]))

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Pokecaカード一覧").sheet1

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("🔍 トップページを読み込み中...")
driver.get("https://pokeca-chart.com/")
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

html = driver.page_source
driver.quit()

soup = BeautifulSoup(html, "html.parser")
cards = soup.find_all("div", class_="cp_card04")
card_urls = []
for card in cards:
    a_tag = card.find("a", href=True)
    if a_tag:
        href = a_tag["href"]
        if href.startswith("https://pokeca-chart.com/s"):
            card_urls.append(href)
card_urls = list(set(card_urls))[:100]
print(f"✅ カードURL取得数: {len(card_urls)} 件")

results = []
for url in card_urls:
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.find("h1").text.strip() if soup.find("h1") else "不明"

        img_tag = soup.find("img")
        img_url = img_tag["src"] if img_tag else ""
        full_img_url = img_url if img_url.startswith("http") else "https://pokeca-chart.com" + img_url
        img_formula = f'=IMAGE("{full_img_url}")' if full_img_url else ""

        table = soup.find("table", id="item-price-table")
        b = [""] * 7
        k = [""] * 7
        p = [""] * 7
        if table:
            rows = table.find_all("tr")
            for i, row in enumerate(rows):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    b[i] = cols[1].text.strip()
                    k[i] = cols[2].text.strip()
                    p[i] = cols[3].text.strip()

        results.append({
            "カード名": title,
            "画像": img_formula,
            "URL": url,
            "美品_データ数": b[0], "美品_直近価格": b[1], "美品_最高価格": b[2], "美品_平均価格": b[3], "美品_最低価格": b[4], "美品_騰落率(7日)": b[5], "美品_騰落率(30日)": b[6],
            "キズあり_データ数": k[0], "キズあり_直近価格": k[1], "キズあり_最高価格": k[2], "キズあり_平均価格": k[3], "キズあり_最低価格": k[4], "キズあり_騰落率(7日)": k[5], "キズあり_騰落率(30日)": k[6],
            "PSA10_データ数": p[0], "PSA10_直近価格": p[1], "PSA10_最高価格": p[2], "PSA10_平均価格": p[3], "PSA10_最低価格": p[4], "PSA10_騰落率(7日)": p[5], "PSA10_騰落率(30日)": p[6]
        })
        print(f"✅ 取得完了: {title}")
    except Exception as e:
        print(f"⚠️ スキップ: {url} → {e}")

sheet.clear()
df = pd.DataFrame(results)
set_with_dataframe(sheet, df)
print("✅ Googleスプレッドシートに出力完了！")

conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    charset='utf8mb4'
)
cursor = conn.cursor()

labels = ["データ数", "直近価格", "最高価格", "平均価格", "最低価格", "騰落率(7日)", "騰落率(30日)"]

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
        json.dumps({l: card[f"美品_{l}"] for l in labels}, ensure_ascii=False),
        json.dumps({l: card[f"キズあり_{l}"] for l in labels}, ensure_ascii=False),
        json.dumps({l: card[f"PSA10_{l}"] for l in labels}, ensure_ascii=False),
    ))

conn.commit()
cursor.close()
conn.close()
print("✅ MySQLへの保存も完了しました！")
