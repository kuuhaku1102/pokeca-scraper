import os
import base64
import re
from urllib.parse import urljoin
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://toreca.io/"
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
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def extract_pt(text: str) -> str:
    m = re.search(r"(\d{2,}(?:,\d+)*)", text)
    return m.group(1) if m else ""


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 toreca.io スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.oripa-card a[href]", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("toreca_io_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        cards = page.query_selector_all("div.oripa-card")
        print(f"検出したカード数: {len(cards)}")
        for card in cards:
            try:
                link = card.query_selector("a[href]")
                if not link:
                    continue
                detail_url = link.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()
                if not detail_url or detail_url in existing_urls:
                    continue

                img = link.query_selector("img")
                image_url = ""
                title = "noname"
                if img:
                    image_url = (img.get_attribute("src") or "").strip()
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                    alt = img.get_attribute("alt") or img.get_attribute("title")
                    if alt:
                        title = alt.strip() or title

                pt_el = card.query_selector("span[id$='price']")
                pt_text = pt_el.inner_text().strip() if pt_el else ""
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
