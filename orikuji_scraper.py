from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import base64
import os
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets 認証 ---
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("その他")

# --- 既存データ取得（画像URLで重複チェック） ---
existing_data = sheet.get_all_values()[1:]
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    print("🔍 orikuji スクレイピング開始...")
    page.goto("https://orikuji.com/", timeout=60000, wait_until="networkidle")

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.theme_newarrival")

    if not cards:
        print("🛑 ガチャ情報が見つかりませんでした。")
    else:
        for card in cards:
            a_tag = card.select_one("a")
            title_img = card.select_one("img.el-image__inner")
            price_tag = card.select_one("span.coin-area")

            if not (a_tag and title_img and price_tag):
                continue

            title = title_img.get("alt", "無題").strip()
            image_url = title_img.get("src")
            detail_url = a_tag["href"]
            point = price_tag.get_text(strip=True)

            if image_url.startswith("/"):
                image_url = "https://orikuji.com" + image_url
            if detail_url.startswith("/"):
                detail_url = "https://orikuji.com" + detail_url

            if image_url in existing_image_urls:
                print(f"⏭ スキップ（重複）: {title}")
                continue

            print(f"✅ 取得: {title} / {point}pt")
            results.append([title, image_url, detail_url, point])

    browser.close()

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2
    range_string = f"A{next_row}:D{next_row + len(results) - 1}"
    try:
        sheet.update(range_string, results)
        print(f"📦 {len(results)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {str(e)}")
else:
    print("📭 新規データなし")
