import os
import base64
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://dopa-game.jp/"
SHEET_NAME = "news"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON is missing")
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
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_existing_image_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 1:
            urls.add(row[0].strip())
    return urls


def scrape_banners(existing_urls: set):
    print("🎬 Launching browser and loading page...")
    rows = []
    skipped = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="load")
            # ✅ 非表示状態でもDOMにあればOK
            page.wait_for_selector(".slick-slide img", timeout=15000, state="attached")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return []

        images = page.query_selector_all(".slick-slide img")
        print(f"🖼️ slick-slide images found: {len(images)}")

        for img in images:
            src = img.get_attribute("src")
            if not src:
                continue
            img_url = urljoin(BASE_URL, src.strip())

            # 親の a タグから href を取得
            a_tag = img.evaluate_handle("node => node.closest('a')")
            href = a_tag.get_property("href").json_value() if a_tag else BASE_URL
            link_url = href.strip() if href else BASE_URL

            if img_url in existing_urls:
                skipped += 1
                continue

            rows.append([img_url, link_url])
            existing_urls.add(img_url)

        browser.close()

    print(f"✅ {len(rows)} new banner(s) found, {skipped} skipped")
    return rows


def main():
    print("🚀 Start")
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 No new banners")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} rows")


if __name__ == "__main__":
    main()
