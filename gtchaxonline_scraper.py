import base64
import os
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://gtchaxonline.com/"
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
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            urls.add(row[2].strip())
    return urls


GACHA_SELECTOR = "div.banner_base"
IMAGE_SELECTOR = "div.image img.current"
TITLE_SELECTOR = "div.name_area"
PT_SELECTOR = "div.gacha_pay div"


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 gtchaxonline.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector(GACHA_SELECTOR, timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("gtchaxonline_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        index = 0
        while True:
            cards = page.query_selector_all(GACHA_SELECTOR)
            if index >= len(cards):
                break
            card = cards[index]
            index += 1

            title_el = card.query_selector(TITLE_SELECTOR)
            title = title_el.inner_text().strip() if title_el else "noname"

            img_el = card.query_selector(IMAGE_SELECTOR)
            image_url = img_el.get_attribute("src") if img_el else ""
            if image_url and image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            pt_el = card.query_selector(PT_SELECTOR)
            pt = pt_el.inner_text().strip() if pt_el else ""

            link_el = card.query_selector("a")
            detail_url = link_el.get_attribute("href") if link_el else ""
            if detail_url and detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)

            if not detail_url:
                try:
                    card.click()
                    page.wait_for_load_state("networkidle")
                    detail_url = page.url
                    page.go_back()
                    page.wait_for_load_state("networkidle")
                except Exception as exc:
                    print(f"❌ 詳細URL取得失敗: {exc}")
                    continue

            if detail_url in existing_urls:
                print(f"⏭ スキップ（重複）: {title}")
                continue

            print(f"✅ 取得: {title}")
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
