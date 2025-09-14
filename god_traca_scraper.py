import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://god-traca.online/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
ITEM_SELECTOR = "div.productWrapStyle"
IMAGE_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")


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
            url = row[2].strip()
            if url:
                urls.add(url)
    return urls


def wait_for_all_items(page) -> None:
    """Scroll and wait until item count no longer increases."""
    prev_count = 0
    start_time = time.time()
    while True:
        count = page.locator(ITEM_SELECTOR).count()
        if count > prev_count:
            prev_count = count
            start_time = time.time()
        else:
            if time.time() - start_time > 10:
                break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)


def parse_items(page) -> List[dict]:
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.productWrapStyle').forEach(el => {
                const fig = el.querySelector('figure');
                let image = '';
                if (fig && fig.style.backgroundImage) {
                    const m = fig.style.backgroundImage.match(/url\(("|')?(.*?)\1\)/);
                    if (m) image = m[2];
                }
                if (!image) {
                    const img = el.querySelector('img');
                    if (img) image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                }
                const title = el.getAttribute('title') || '';
                let url = '';
                const a = el.querySelector('a[href]');
                if (a) url = a.getAttribute('href') || '';
                if (!url) {
                    const id = el.id || '';
                    const m = id.match(/(\d+)-Wrap/);
                    if (m) url = `/gacha/${m[1]}`;
                }
                let pt = '';
                const ptP = el.querySelector('div.gacha-point p:nth-child(2)');
                if (ptP) pt = ptP.textContent.trim();
                results.push({ title, image, url, pt });
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
        print("🔍 god-traca.online スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector(ITEM_SELECTOR, timeout=60000)
            wait_for_all_items(page)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("god_traca_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = parse_items(page)
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "").strip()

        if not detail_url:
            continue
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if detail_url in existing_urls:
            continue

        pt_value = re.sub(r"[^0-9]", "", pt_text)
        rows.append([title, image_url, detail_url, pt_value])
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
