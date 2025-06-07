import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://ichica.co/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
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
    """Return set of detail URLs already in the sheet (3rd column)."""
    records = sheet.get_all_values()
    url_set = set()
    for row in records:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("🔍 ichica.co スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=120000)
            page.wait_for_timeout(7000)  # JS描画待機
            items = page.query_selector_all('div.clickable-element.bubble-element.Group.cmgaAm')
            print(f"🟢 検出数: {len(items)}")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("ichica_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        for card in items:
            # メイン画像
            img = card.query_selector('div.bubble-element.Image.cmgaBaP img')
            image_url = img.get_attribute('src') if img else ""
            title = img.get_attribute('alt') if (img and img.get_attribute('alt')) else (image_url.split("/")[-1] if image_url else "noname")
            # PT
            pt_el = card.query_selector('div.bubble-element.Text.cmgaAy')
            pt = pt_el.inner_text().strip() if pt_el else ""
            # 詳細URL（progress-barのidから抽出）
            progress_div = card.query_selector('div.progress-bar')
            detail_id = None
            if progress_div:
                progress_id = progress_div.get_attribute('id')
                m = re.search(r'dynamic-progress-bar([0-9a-z]+)', progress_id or "")
                if m:
                    detail_id = m.group(1)
            detail_url = (
                f"https://ichica.co/pack/{detail_id}?section=main%20list&sort=recommended&category=Pokemon&lotteryprice=&lotterycard={detail_id}&lotterytab=all"
                if detail_id else ""
            )

            # 必須要素が無い場合はskip
            if not (title and image_url and detail_url):
                continue
            # 重複skip
            if detail_url in existing_urls:
                continue

            rows.append([title, image_url, detail_url, pt])
            existing_urls.add(detail_url)
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
