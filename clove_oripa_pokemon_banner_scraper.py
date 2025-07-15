import os
import base64
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa.clove.jp"
TARGET_URL = f"{BASE_URL}/oripa/Pokemon"
SHEET_NAME = "news"
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


def fetch_existing_image_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 1:
            urls.add(row[0].strip())
    return urls


def decode_next_image(url: str) -> str:
    """Decode Next.js image URLs to the original source."""
    if url.startswith("/_next/image") and "url=" in url:
        query = parse_qs(urlparse(url).query).get("url")
        if query:
            return unquote(query[0])
    return url


def scrape_banners(existing_urls: set):
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # reveal additional slides by clicking the next button if present
            for _ in range(10):
                next_btn = page.query_selector(".swiper-button-next")
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_timeout(500)

            slides = page.query_selector_all(".swiper-wrapper .swiper-slide")
        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            browser.close()
            return rows

        for slide in slides:
            img = slide.query_selector("img")
            if not img:
                continue

            src = img.get_attribute("alt") or img.get_attribute("src")
            if not src:
                continue
            src = decode_next_image(src)
            if src.startswith("/"):
                src = urljoin(BASE_URL, src)

            if src not in existing_urls:
                rows.append([src, TARGET_URL])
                existing_urls.add(src)

        browser.close()

    print(f"✅ {len(rows)} 件の新規バナー")
    return rows


def main() -> None:
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 新規データなし")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 {len(rows)} 件追記完了")


if __name__ == "__main__":
    main()
