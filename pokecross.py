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
existing_data = sheet.get_all_values()[1:]  # 1行目はヘッダーと仮定
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    )
    page = context.new_page()
    print("🔍 pokeca スクレイピング開始...")

    try:
        page.goto("https://pokeca.com/", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=60000)
    except Exception as e:
        print(f"🛑 ページ読み込みエラー: {str(e)}")
        page.screenshot(path="error_screenshot.png")
        html = page.content()
        with open("error_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        browser.close()
        exit()

    # デバッグ用HTML保存
    html = page.content()
    with open("page_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    try:
        page.wait_for_selector("div.original-packs-card", timeout=10000)
    except Exception:
        print("🛑 要素が読み込まれませんでした。")
        page.screenshot(path="error_screenshot.png")
        html = page.content()
        with open("error_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        browser.close()
        exit()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.original-packs-card")

    for card in cards:
        a_tag = card.select_one("a.link-underline")
        img_tag = card.select_one("img.card-img-top")
        pt_tag = card.select_one("p.point-amount")

        if not (a_tag and img_tag and pt_tag):
            continue

        title = img_tag.get("alt", "無題").strip()
        image_url = img_tag["src"]
        detail_url = a_tag["href"]
        pt_text = pt_tag.get_text(strip=True).replace("/1回", "").strip()

        if image_url.startswith("/"):
            image_url = "https://pokeca.com" + image_url
        if detail_url.startswith("/"):
            detail_url = "https://pokeca.com" + detail_url

        if image_url in existing_image_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        print(f"✅ 取得: {title} / {pt_text}")
        results.append([title, image_url, detail_url, pt_text])

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
