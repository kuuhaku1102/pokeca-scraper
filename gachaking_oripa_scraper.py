import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://gachaking-oripa.com/index"
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
    if not url:
        return ""
    if url.startswith("/"):
        url = urljoin("https://gachaking-oripa.com", url)
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            u = row[2].strip()
            if u:
                urls.add(normalize_url(u))
    return urls


def scroll_to_bottom(page, max_scrolls=20, pause_ms=500):
    last_height = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        height = page.evaluate("document.body.scrollHeight")
        if height == last_height:
            break
        last_height = height


def parse_items(page) -> List[dict]:
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.items.series-guest-manage-height').forEach(item => {
                const linkEl = item.querySelector('a[link]');
                const url = linkEl ? linkEl.getAttribute('link') : '';
                const img = item.querySelector('.bgimg img');
                const image = img ? (img.getAttribute('data-original') || img.getAttribute('src') || '') : '';
                const title = img ? (img.getAttribute('alt') || img.getAttribute('title') || '').trim() : '';
                const ptEl = item.querySelector('.btn-box span.second-text');
                const pt = ptEl ? ptEl.textContent.trim() : '';
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
        print("🔍 gachaking-oripa スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.items', timeout=60000)
            scroll_to_bottom(page)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            with open("gachaking_oripa_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        items = parse_items(page)
        browser.close()

    for item in items:
        detail_url = normalize_url(item.get("url", "").strip())
        if not detail_url or detail_url in existing_urls:
            continue

        image_url = item.get("image", "").strip()
        if image_url.startswith("/"):
            image_url = urljoin("https://gachaking-oripa.com", image_url)

        title = item.get("title", "").strip() or "noname"
        pt_text = re.sub(r"[^0-9]", "", item.get("pt", ""))

        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)
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
