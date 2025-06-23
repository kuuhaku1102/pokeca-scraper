import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://blackgacha.com/"
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
        print("🔍 blackgacha.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.card", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("blackgacha_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.card.border-0').forEach(card => {
                    const link = card.querySelector('a[href]');
                    if (!link) return;
                    const url = link.href;
                    let image = '';
                    const ratio = card.querySelector('.ratio-image-component');
                    if (ratio && ratio.style.backgroundImage) {
                        const m = ratio.style.backgroundImage.match(/url\(("|')?(.*?)\1\)/);
                        if (m) image = m[2];
                    }
                    if (!image) {
                        const img = card.querySelector('img');
                        if (img) image = img.src || img.getAttribute('data-src') || '';
                    }
                    let title = link.getAttribute('title') || '';
                    if (!title) {
                        const img = card.querySelector('img');
                        if (img && img.alt) title = img.alt;
                    }
                    if (!title) {
                        const tEl = card.querySelector('.card-body');
                        if (tEl) {
                            const t = tEl.textContent.trim();
                            if (t) title = t.split('\n')[0].trim();
                        }
                    }
                    let pt = '';
                    const ptEl = card.querySelector('.card-body .text-warning');
                    if (ptEl) {
                        const txt = ptEl.textContent.replace(/,/g, '');
                        const m = txt.match(/(\d+)/);
                        if (m) pt = m[1];
                    }
                    results.push({ title, image, url, pt });
                });
                return results;
            }
            """
        )

        for item in items:
            detail_url = item.get("url", "").strip()
            image_url = item.get("image", "").strip()
            title = item.get("title", "noname").strip() or "noname"
            pt_value = item.get("pt", "").strip()

            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            if detail_url in existing_urls:
                continue

            rows.append([title, image_url, detail_url, pt_value])
            existing_urls.add(detail_url)

        browser.close()
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
