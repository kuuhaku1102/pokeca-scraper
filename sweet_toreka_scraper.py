import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://sweet-toreka.com/"
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


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 sweet-toreka スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.col-12", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("sweet_toreka_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.col-12.col-md-6.col-lg-4').forEach(card => {
                    const a = card.querySelector('a[href]');
                    const detail_url = a ? a.getAttribute('href') || '' : '';
                    let image = '';
                    const ratio = card.querySelector('.ratio-image-component');
                    if (ratio && ratio.style.backgroundImage) {
                        const m = ratio.style.backgroundImage.match(/url\(["']?(.*?)["']?\)/);
                        if (m) image = m[1];
                    }
                    if (!image) {
                        const img = card.querySelector('img');
                        if (img) image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    }
                    let title = '';
                    const tEl = card.querySelector('[data-bs-toggle="tooltip"][title]');
                    if (tEl) title = tEl.getAttribute('title') || '';
                    if (!title && a) title = a.textContent.trim();
                    const ptEl = card.querySelector('span.fs-3');
                    const pt = ptEl ? ptEl.textContent.trim() : '';
                    results.push({ title, image, url: detail_url, pt });
                });
                return results;
            }
            """
        )
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if not detail_url or detail_url in existing_urls:
            continue

        image_url = item.get("image", "").strip()
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "")
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
