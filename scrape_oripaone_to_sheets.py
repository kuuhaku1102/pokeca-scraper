import os
import base64
import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from google.oauth2.service_account import Credentials

def save_to_sheet(data):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials_json = os.environ.get("GSHEET_JSON")
    if not credentials_json:
        raise Exception("❌ 環境変数 'GSHEET_JSON' が見つかりません")

    with open("credentials.json", "wb") as f:
        f.write(base64.b64decode(credentials_json))

    credentials = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    gc = gspread.authorize(credentials)
    sheet = gc.open("oripaone").sheet1

    sheet.clear()
    sheet.append_row(["タイトル", "画像URL", "詳細URL"])
    for row in data:
        sheet.append_row([row['title'], row['img'], row['url']])

def scrape_oripaone():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get("https://oripaone.jp/")
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = []
    cards = soup.select(".grid > div.relative")
    for card in cards:
        a_tag = card.find("a")
        if a_tag:
            href = a_tag.get("href")
            url = f"https://oripaone.jp{href}"
            img_tag = a_tag.find("img")
            img = img_tag.get("src") if img_tag else ""
            title = img_tag.get("alt") if img_tag else ""
            data.append({"title": title.strip(), "img": img.strip(), "url": url.strip()})

    driver.quit()
    return data

def main():
    print("🔍 oripaone スクレイピング開始...")
    data = scrape_oripaone()
    print(f"✅ 取得件数: {len(data)} 件")
    save_to_sheet(data)
    print("✅ スプレッドシート出力完了")

if __name__ == "__main__":
    main()
