import os
import base64
import re
from urllib.parse import urljoin
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ====== 設定値 ======
BASE_URL = "https://dopa-game.jp/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

# gachaリストを囲むdivと個々のリンクaタグのセレクタ
GACHA_CONTAINER_SELECTOR = "div.css-1flrjkp"  # ガチャ一覧全体
GACHA_LINK_SELECTOR = "a.css-4g6ai3"          # 各ガチャへのリンク
IMAGE_SELECTOR = "img.chakra-image"           # サムネイル画像
PT_SELECTOR = "p.chakra-text"                 # PT表示テキスト

def save_credentials() -> str:
    """GSHEET_JSONをデコードして認証ファイルとして保存"""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
    """Googleスプレッドシートの 'その他' シートを返す"""
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    if not SPREADSHEET_URL:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)

def fetch_existing_urls(sheet) -> set:
    """既存URL（3列目）をsetで取得"""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set

def extract_pt(text: str) -> str:
    """'123PT' などのテキストから数字部分を抽出"""
    m = re.search(r"(\d+(?:,\d+)*)", text)
    return m.group(1) if m else text.strip()

def scrape_items(existing_urls: set) -> List[List[str]]:
    """Playwrightでdopa-game.jpをスクレイピング"""
    rows: List[List[str]] = []
    with sync_playwright() as p:
        # headless=Falseで画面表示（デバッグしやすい）
        browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
        # User-Agent偽装でbot対策回避
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        print("🔍 dopa-game.jp スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("body", timeout=60000)
            # HTMLの内容をprint（Cloudflare対策などでガチャリストが表示されているかデバッグ用）
            print("========= HTML内容抜粋 =========")
            print(page.content()[:2000])  # 先頭2000文字だけ表示
            print("===============================")
            page.wait_for_selector(GACHA_CONTAINER_SELECTOR, timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows

        anchors = page.query_selector_all(f"{GACHA_CONTAINER_SELECTOR} {GACHA_LINK_SELECTOR}")
        print(f"検出したガチャ数: {len(anchors)}")
        for a in anchors:
            try:
                detail_url = a.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()
                if not detail_url or detail_url in existing_urls:
                    continue

                img = a.query_selector(IMAGE_SELECTOR)
                image_url = ""
                title = "noname"
                if img:
                    image_url = (img.get_attribute("src") or "").strip()
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                    title = (img.get_attribute("alt") or "").strip() or title
                if not title:
                    txt = a.inner_text().strip()
                    if txt:
                        title = txt

                pt_tag = a.query_selector(PT_SELECTOR)
                pt_text = pt_tag.inner_text().strip() if pt_tag else ""
                pt_value = extract_pt(pt_text)

                rows.append([title, image_url, detail_url, pt_value])
                existing_urls.add(detail_url)
            except Exception as exc:
                print(f"⚠ 取得スキップ: {exc}")
                continue
        browser.close()
    return rows

def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if not rows:
        print("📭 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    except Exception as exc:
        print(f"❌ スプレッドシート書き込み失敗: {exc}")

if __name__ == "__main__":
    main()
