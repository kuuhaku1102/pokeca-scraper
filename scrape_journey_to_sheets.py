import os
import base64
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://journey-gacha.com/"
LIST_URL = urljoin(BASE_URL, "user/packList")
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

def save_credentials() -> str:
    """Decode GSHEET_JSON and save to credentials.json."""
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
    """Return set of detail URLs already recorded (3rd column)."""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set

def decode_image_url(src: str) -> str:
    """Extract the actual image URL from the _next/image query."""
    if not src:
        return ""
    if src.startswith("/"):
        src = urljoin(BASE_URL, src)
    parsed = urlparse(src)
    qs = parse_qs(parsed.query)
    if "url" in qs and qs["url"]:
        return unquote(qs["url"][0])
    return src

def scrape_items(existing_urls: set) -> List[List[str]]:
    """Scrape pack info from journey-gacha and return new rows."""
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 journey-gacha スクレイピング開始...")
        try:
            page.goto(LIST_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector("div.packList__item", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            with open("journey_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        items = page.evaluate(
            """
            () => {
                const arr = [];
                document.querySelectorAll('div.packList__item').forEach(el => {
                    arr.push({
                        id: el.getAttribute('data-pack-id') || '',
                        name: el.getAttribute('data-pack-name') || 'noname',
                        img: el.querySelector('img')?.getAttribute('src') || '',
                        pt: el.querySelector('p.packList__pt-txt')?.textContent || ''
                    });
                });
                return arr;
            }
            """
        )
        html = page.content()
        browser.close()

    for item in items:
        detail_url = urljoin(BASE_URL, f"pack/{item['id']}") if item['id'] else ''
        if not detail_url or detail_url in existing_urls:
            if detail_url in existing_urls:
                print(f"⏭ スキップ（重複）: {item['name']}")
            continue
        image_url = decode_image_url(item.get('img', ''))
        pt_text = item.get('pt', '').replace(',', '').strip()
        title = item.get('name', 'noname').strip() or 'noname'
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)
        print(f"✅ 取得: {title}")

    with open("journey_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
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
