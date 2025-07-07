import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://dopa-game.jp/"
SHEET_NAME = "news"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

BANNER_IMG_SELECTOR = "img.chakra-image"  # より正確なセレクターに変更


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
        if len(row) >= 2:
            urls.add(row[1].strip())
    return urls


def scrape_banners(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 dopa-game.jp banner scraping...")
        page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        try:
            page.wait_for_selector(BANNER_IMG_SELECTOR, timeout=60000, state="visible")
        except Exception as exc:
            print(f"🛑 page load failed: {exc}")
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            return rows
        imgs = page.query_selector_all(BANNER_IMG_SELECTOR)
        print(f"found {len(imgs)} banner images")
        for img in imgs:
            # クローン要素はスキップ
            if img.evaluate("el => el.closest('.slick-slide')?.classList.contains('slick-cloned')"):
                continue
            src = (img.get_attribute("src") or "").strip()
            if not src:
                continue
            if src.startswith("/"):
                src = urljoin(BASE_URL, src)
            if src in existing_urls:
                continue
            alt = (img.get_attribute("alt") or "noname").strip() or "noname"
            rows.append([alt, src, BASE_URL, ""])
            existing_urls.add(src)
        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 No new banners")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} rows appended")
    except Exception as exc:
        print(f"❌ Failed to write to sheet: {exc}")


if __name__ == "__main__":
    main()
