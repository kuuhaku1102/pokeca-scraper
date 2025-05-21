import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa.xyz/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

GACHA_GROUP_SELECTOR = ".gacha__group"


def save_credentials() -> str:
    """Decode service account JSON from env and save to file."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return gspread worksheet from SPREADSHEET_URL."""
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
    """Return set of detail page URLs already in sheet."""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def scroll_to_bottom(page, max_scrolls=20, pause_ms=500):
    """Scroll page to bottom to load dynamic content."""
    last_height = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        height = page.evaluate("document.body.scrollHeight")
        if height == last_height:
            break
        last_height = height


def extract_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 oripa.xyz スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector(GACHA_GROUP_SELECTOR, timeout=60000)
            scroll_to_bottom(page)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            with open("oripa_xyz_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        groups = page.query_selector_all(GACHA_GROUP_SELECTOR)
        print(f"検出されたガチャ数: {len(groups)}")
        for g in groups:
            try:
                link = g.query_selector("a.gacha__group_link")
                if not link:
                    continue
                detail_url = link.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()
                if not detail_url or detail_url in existing_urls:
                    continue

                img = g.query_selector("img")
                image_url = ""
                title = ""
                if img:
                    image_url = img.get_attribute("data-src") or img.get_attribute("src") or ""
                    title = img.get_attribute("alt") or ""
                if image_url.startswith("/"):
                    image_url = urljoin(BASE_URL, image_url)
                if not title:
                    title = link.inner_text().strip()
                title = title or "noname"

                pt_tag = g.query_selector(".gacha__price_total")
                pt_text = pt_tag.inner_text().strip() if pt_tag else ""
                pt_value = re.sub(r"[^0-9]", "", pt_text)

                rows.append([title, image_url, detail_url, pt_value])
                existing_urls.add(detail_url)
            except Exception as exc:
                print(f"⚠ データ取得失敗: {exc}")
                continue

        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = extract_items(existing_urls)
    if not rows:
        print("📭 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    except Exception as exc:
        print(f"❌ 書き込みエラー: {exc}")


if __name__ == "__main__":
    main()
