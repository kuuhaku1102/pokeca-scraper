import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripalette.jp/"
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
            url = row[2].strip()
            if url:
                urls.add(url)
    return urls


def wait_until_banners(page, min_count: int = 3, max_wait: int = 15) -> int:
    import time

    start = time.time()
    last_count = 0
    stable = 0
    while True:
        count = page.eval_on_selector_all("div.banner_base.banner", "els => els.length")
        if count == last_count and count >= min_count:
            stable += 1
        else:
            stable = 0
        last_count = count
        if stable >= 2 or time.time() - start > max_wait:
            break
        time.sleep(0.7)
    return count


def parse_items(page) -> List[dict]:
    items = page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.banner_base.banner').forEach(box => {
                const img = box.querySelector('img.current') || box.querySelector('img');
                const image = img ? (img.getAttribute('src') || '') : '';
                let title = img ? (img.getAttribute('alt') || img.getAttribute('title') || '').trim() : '';
                if (!title) {
                    const tEl = box.querySelector('.name_area-info') || box.querySelector('.name_area');
                    if (tEl) title = tEl.textContent.trim();
                }
                let url = '';
                const a = box.querySelector('a[href]');
                if (a) url = a.getAttribute('href') || '';
                if (!url) {
                    const m = image.match(/\/pack\/(\d+)/);
                    if (m) url = `/pack/${m[1]}`;
                }
                let pt = '';
                const ptEl = box.querySelector('.point') || box.querySelector('.point_area') || box.querySelector('div.point');
                if (ptEl) {
                    const txt = ptEl.textContent.replace(/,/g, '');
                    const m2 = txt.match(/(\d+)/);
                    if (m2) pt = m2[1];
                }
                results.push({ title, image, url, pt });
            });
            return results;
        }
        """
    )
    return items


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 oripalette.jp スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.banner_base.banner", timeout=60000)
            wait_until_banners(page)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("oripalette_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = parse_items(page)
        for item in items:
            detail_url = item.get("url", "").strip()
            image_url = item.get("image", "").strip()
            title = item.get("title", "noname").strip() or "noname"
            pt_text = item.get("pt", "").strip()

            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            if detail_url in existing_urls:
                continue

            rows.append([title, image_url, detail_url, pt_text])
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
