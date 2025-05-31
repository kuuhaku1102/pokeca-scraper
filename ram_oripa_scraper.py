import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://ram-oripa.com/"
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
    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not spreadsheet_url:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(spreadsheet_url)
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
        print("🔍 ram-oripa スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("img.gacha-img", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            with open("ram_oripa_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('img.gacha-img').forEach(img => {
                    const a = img.closest('a');
                    if (!a) return;
                    const detail_url = a.href || '';
                    let title = '';
                    const nameEl = a.querySelector('.gacha-name') || a.querySelector('.gacha-title');
                    if (nameEl) {
                        title = nameEl.textContent.trim();
                    }
                    if (!title) {
                        title = img.getAttribute('alt') || '';
                    }
                    const priceEl = a.querySelector('.gacha-price') || a.querySelector('.gacha-pt');
                    const pt = priceEl ? priceEl.textContent.trim() : '';
                    results.push({title, image: img.src, url: detail_url, pt});
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

        image_url = item.get("image", "")
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
