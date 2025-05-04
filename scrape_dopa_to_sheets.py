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
sheet = spreadsheet.worksheet("dopa")

# --- 重複チェック用画像URL取得 ---
existing_data = sheet.get_all_values()[1:]
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print("🔍 dopa スクレイピング開始...")
    page.goto("https://dopa-game.jp/", timeout=30000)

    try:
        page.wait_for_selector("div.css-1flrjkp a.css-4g6ai3 img", timeout=30000)
    except Exception:
        print("🛑 imgタグが読み込まれませんでした。")
        browser.close()
        exit()

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.css-1flrjkp a.css-4g6ai3")

    for card in cards:
        img_tag = card.select_one("img")
        if not img_tag:
            continue

        title = img_tag.get("alt", "無題").strip()
        image_url = img_tag["src"]
        detail_url = card["href"]

        if image_url.startswith("/"):
            image_url = "https://dopa-game.jp" + image_url
        if detail_url.startswith("/"):
            detail_url = "https://dopa-game.jp" + detail_url

        if image_url in existing_image_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        print(f"✅ 取得: {title}")
        results.append([title, image_url, detail_url])

    browser.close()

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2
    sheet.update(f"A{next_row}", results)
    print(f"📦 {len(results)} 件追記完了")
else:
    print("📭 新規データなし")
