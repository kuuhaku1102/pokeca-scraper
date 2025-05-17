import base64
import os
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def strip_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

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
existing_image_urls = {strip_query(row[1]) for row in existing_data if len(row) > 1}

results = []
html = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    print("🔍 ciel-toreca スクレイピング開始...")

    try:
        page.goto("https://ciel-toreca.com/", timeout=60000, wait_until="networkidle")
    except Exception as e:
        print(f"🛑 ページ読み込みエラー: {str(e)}")
        html = page.content()
        browser.close()
        exit()

    page.wait_for_selector("div.cursor-pointer", timeout=60000)
    html = page.content()
    items = page.evaluate(
        """
        () => {
            const cards = document.querySelectorAll('div.cursor-pointer a[href*="/gacha/"]');
            const results = [];
            cards.forEach(a => {
                const img = a.querySelector('img');
                if (!img) return;
                const image = img.getAttribute('src') || img.getAttribute('data-src');
                const title = img.getAttribute('alt') || img.getAttribute('title') || '';
                const ptEl = a.querySelector('div.flex.items-center span.font-semibold');
                const pt = ptEl ? ptEl.textContent.trim() + 'PT' : '';
                results.push({ title, image, url: a.href, pt });
            });
            return results;
        }
        """
    )

    browser.close()

    if not items:
        print("📭 画像情報が取得できませんでした。")
    else:
        print(f"📦 {len(items)} 件の画像を取得")
        for item in items:
            title = item["title"].strip() if item["title"].strip() else "noname"
            image_url = item["image"]
            detail_url = item["url"]

            if image_url.startswith("/"):
                image_url = "https://ciel-toreca.com" + image_url
            if detail_url.startswith("/"):
                detail_url = "https://ciel-toreca.com" + detail_url

            norm_url = strip_query(image_url)
            if norm_url in existing_image_urls:
                print(f"⏭ スキップ（重複）: {title}")
                continue

            print(f"✅ 取得: {title}")
            results.append([title, image_url, detail_url, item.get("pt", "")])

# --- スプレッドシートに追記 ---
if results:
    try:
        sheet.append_rows(results, value_input_option='USER_ENTERED')
        print(f"📥 {len(results)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {str(e)}")
else:
    print("📭 新規データなし")

# --- デバッグHTML保存 ---
if html:
    with open("ciel_page_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
