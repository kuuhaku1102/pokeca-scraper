from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import base64
import os
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import urlparse

# --- クエリを除いたURL比較用関数 ---
def strip_query(url):
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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    print("🔍 orikuji スクレイピング開始...")

    try:
        page.goto("https://orikuji.com/", timeout=60000, wait_until="networkidle")
        page.wait_for_selector("img.el-image__inner", timeout=30000)  # 確実な描画待機
        page.wait_for_timeout(2000)  # 念のため2秒待機
    except Exception as e:
        print(f"🛑 ページ読み込みエラー: {str(e)}")
        page.screenshot(path="error_screenshot.png")
        with open("error_page.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        browser.close()
        exit()

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.white-box.theme_newarrival")

    if not cards:
        print("🛑 ガチャ情報が見つかりませんでした。")
        with open("page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
    else:
        print(f"📦 {len(cards)} 件のガチャが見つかりました。")
        for card in cards:
            try:
                a_tag = card.select_one("a")
                img_tag = card.select_one("img.el-image__inner")
                pt_tag = card.select_one("span.coin-area")

                if not (a_tag and img_tag and pt_tag):
                    print("⚠️ 要素不足: ", {
                        "a_tag": bool(a_tag),
                        "img_tag": bool(img_tag),
                        "pt_tag": bool(pt_tag)
                    })
                    continue

                title = img_tag.get("alt", "無題").strip()
                image_url = img_tag.get("src", "")
                detail_url = a_tag.get("href", "")
                pt_text = pt_tag.get_text(strip=True)

                if image_url.startswith("/"):
                    image_url = "https://orikuji.com" + image_url
                if detail_url.startswith("/"):
                    detail_url = "https://orikuji.com" + detail_url

                norm_url = strip_query(image_url)

                if norm_url in existing_image_urls:
                    print(f"⏭ スキップ（重複）: {title}")
                    continue

                print(f"✅ 取得: {title} / {pt_text}pt")
                results.append([title, image_url, detail_url, pt_text])
            except Exception as e:
                print(f"❌ 処理エラー: {str(e)}")
                continue

    browser.close()

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2
    range_string = f"A{next_row}:D{next_row + len(results) - 1}"
    try:
        sheet.update(range_string, results)
        print(f"📥 {len(results)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {str(e)}")
else:
    print("📭 新規データなし")
    print(f"🔎 登録済みURL数: {len(existing_image_urls)}")
