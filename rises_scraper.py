import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://rises.jp/product"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"


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
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def parse_items(page) -> List[dict]:
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.gacha-item').forEach(card => {
                const link = card.querySelector('a[href]');
                const img = link ? link.querySelector('img') : null;
                const url = link ? link.href : '';
                const image = img ? (img.getAttribute('src') || '') : '';
                const title = img ? (img.getAttribute('alt') || '').trim() : '';
                let pt = '';
                const span = card.querySelector('span.gacha-price');
                if (span) pt = span.textContent.replace(/\s+/g, '');
                results.push({title, image, url, pt});
            });
            return results;
        }
        """
    )


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 rises.jp スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_selector('div.gacha-item', timeout=120000)
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.gacha-item', timeout=60000)
        except Exception as exc:
            html = page.content()
            with open("rises_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            print(f"🛑 ページ読み込み失敗: {exc}")
            return rows

        items = parse_items(page)
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip() or "noname"
        pt_text = re.sub(r"[^0-9,]", "", item.get("pt", ""))

        if detail_url.startswith("/"):
            detail_url = urljoin("https://rises.jp", detail_url)
        if image_url.startswith("/"):
            image_url = urljoin("https://rises.jp", image_url)

        norm_url = normalize_url(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(norm_url)
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
