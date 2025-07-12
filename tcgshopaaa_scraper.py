import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://tcgshopaaa.com/"
DETAIL_URL = "https://tcgshopaaa.com/detail"
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


def normalize_url(url: str) -> str:
    if url.startswith("/"):
        url = urljoin(BASE_URL, url)
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            u = row[2].strip()
            if u:
                urls.add(normalize_url(u))
    return urls


def parse_items(page) -> List[dict]:
    return page.evaluate(
        f"""
        () => {{
            const results = [];
            document.querySelectorAll('form[id^="gacha-form-"]').forEach(form => {{
                const id = form.getAttribute('id').replace('gacha-form-', '');
                const container = form.parentElement;
                const img = container.querySelector('.gacha-image img');
                const title = img ? (img.getAttribute('alt') || img.getAttribute('title') || '').trim() : '';
                const image = img ? img.getAttribute('src') || '' : '';
                const priceEl = container.querySelector('.gacha-header .gacha-price');
                let pt = priceEl ? priceEl.textContent : '';
                pt = pt.replace(/[^0-9]/g, '');
                const url = id ? '{DETAIL_URL}?gacha_id=' + id : '';
                results.push({{ title, image, url, pt }});
            }});
            return results;
        }}
        """
    )


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 tcgshopaaa.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('form[id^="gacha-form-"]', timeout=60000, state="attached")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            if html:
                with open("tcgshopaaa_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
            return rows

        items = parse_items(page)
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip() or "noname"
        pt_text = item.get("pt", "").strip()

        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)

        norm_url = normalize_url(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(norm_url)
    if html:
        with open("tcgshopaaa_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if rows:
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"📥 {len(rows)} 件追記完了")
        except Exception as exc:
            print(f"❌ スプレッドシート書き込み失敗: {exc}")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
