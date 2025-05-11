from playwright.sync_api import sync_playwright
import base64
import os
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import urlparse

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
html = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    print("🔍 orikuji スクレイピング開始...")

    try:
        page.goto("https://orikuji.com/", timeout=60000, wait_until="networkidle")

        # LazyLoad対策でスクロール
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        # ガチャ画像が表示されるまで待機
        page.wait_for_function("""
          () => {
            const imgs = Array.from(document.querySelectorAll("img"));
            return imgs.some(img => (img.getAttribute('src') || img.getAttribute('data-src'))?.includes("/gacha/"));
          }
        """, timeout=20000)
    except Exception as e:
        print(f"🛑 ページ読み込みエラー: {str(e)}")
        page.screenshot(path="debug.png")
        html = page.content()
        browser.close()
        exit()

    html = page.content()
    page.screenshot(path="debug.png", full_page=True)

    # --- JavaScriptで情報抽出 ---
    items = page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll("div.white-box.theme_newarrival")).map(card => {
            const img = card.querySelector('img.el-image__inner');
            const a = card.querySelector('a[href]');
            const pt = card.querySelector('span.coin-area');

            const imageUrl = img?.getAttribute('src') || img?.getAttribute('data-src') || img?.getAttribute('data-original');

            return {
                title: img?.alt || null,
                image: imageUrl,
                url: a?.href || null,
                point: pt?.innerText || null
            };
        }).filter(item => item.image && item.image.includes("/gacha/"));
    }
    """)

    browser.close()

    if not items:
        print("📭 ガチャ情報が取得できませんでした。")
    else:
        print(f"📦 {len(items)} 件のガチャを取得")
        for item in items:
            title = item["title"].strip()
            image_url = item["image"]
            detail_url = item["url"]
            pt_text = item["point"].strip() if item["point"] else ""

            if not image_url or image_url.startswith("data:image/"):
                continue
            if image_url.startswith("/"):
                image_url = "https://orikuji.com" + image_url
            if detail_url and detail_url.startswith("/"):
                detail_url = "https://orikuji.com" + detail_url

            norm_url = strip_query(image_url)
            if norm_url in existing_image_urls:
                print(f"⏭ スキップ（重複）: {title}")
                continue

            print(f"✅ 取得: {title} / {pt_text}pt")
            results.append([title, image_url, detail_url, pt_text])

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2
    try:
        sheet.update(range_name=f"A{next_row}:D{next_row + len(results) - 1}", values=results)
        print(f"📥 {len(results)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {str(e)}")
else:
    print("📭 新規データなし")
    print(f"🔎 登録済みURL数: {len(existing_image_urls)}")

# --- デバッグHTML保存（任意） ---
if html:
    try:
        with open("page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"❌ デバッグHTML保存失敗: {str(e)}")
