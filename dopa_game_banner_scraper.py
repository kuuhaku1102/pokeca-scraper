import os
import base64
import time
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://dopa-game.jp/"
SHEET_NAME = "news"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
BANNER_IMG_SELECTOR = "div.slick-slider img"


def save_credentials() -> str:
    print("📦 Saving credentials from environment variable")
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("❌ GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    print("✅ Credentials saved as credentials.json")
    return "credentials.json"


def get_sheet():
    print("📡 Initializing Google Sheets API")
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)

    if not SPREADSHEET_URL:
        raise RuntimeError("❌ SPREADSHEET_URL environment variable is missing")

    print("📊 Opening spreadsheet by URL")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    print(f"✅ Sheet '{SHEET_NAME}' loaded")
    return sheet


def fetch_existing_image_urls(sheet) -> set:
    print("🔎 Fetching existing imgURL entries from sheet")
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:  # skip header
        if len(row) >= 1:
            urls.add(row[0].strip())
    print(f"📚 {len(urls)} existing URLs found")
    return urls


def scrape_banners(existing_urls: set) -> List[List[str]]:
    print("🕷️ Starting Playwright banner scraping...")
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            print(f"🌐 Navigating to {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            print("➡️ Advancing slider via .slick-next click")
            for _ in range(5):
                try:
                    page.click(".slick-next")
                except:
                    pass  # ignore if not clickable yet
                time.sleep(1)

            print("🧠 Extracting banner images via JS evaluation")
            banner_data = page.evaluate("""
                () => {
                    const imgs = Array.from(document.querySelectorAll('img.chakra-image'));
                    return imgs.map(img => ({
                        src: img.src,
                        alt: img.alt || 'noname'
                    }));
                }
            """)

            if not banner_data:
                raise RuntimeError("❌ No banner images extracted via JS")

        except Exception as exc:
            print(f"🛑 page load failed: {exc}")
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("📝 debug.html written for inspection")
            browser.close()
            return rows

        print(f"✅ Extracted {len(banner_data)} images via JS")

        for item in banner_data:
            src = item["src"].strip()
            if not src or src in existing_urls:
                continue
            rows.append([src, BASE_URL])
            existing_urls.add(src)

        browser.close()
        print(f"📦 Scraped {len(rows)} new banner(s)")
    return rows


def main() -> None:
    print("🚀 Start main process")
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)

    if not rows:
        print("📭 No new banners")
        return

    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} rows appended to sheet")
    except Exception as exc:
        print(f"❌ Failed to write to sheet: {exc}")


if __name__ == "__main__":
    main()
