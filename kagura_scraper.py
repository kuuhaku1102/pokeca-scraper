import os
import base64
import re
from urllib.parse import urljoin
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://kagura-tcg.com/"
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
        print("🔍 kagura-tcg.com スクレイピング開始...")

        def scroll_to_load_all(max_tries: int = 20, step: int = 800) -> None:
            prev_height = 0
            for _ in range(max_tries):
                page.evaluate(f"window.scrollBy(0, {step});")
                page.wait_for_timeout(500)
                curr = page.evaluate("document.documentElement.scrollHeight")
                if curr == prev_height:
                    break
                prev_height = curr

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=60000)
            scroll_to_load_all()
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open('kagura_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('a[href*="/gacha/"]').forEach(a => {
                    const card = a.querySelector('div.flex.flex-col.cursor-pointer') || a;
                    let image = '';
                    const bg = card.querySelector('div[style*="background-image"]');
                    if (bg) {
                        const style = bg.getAttribute('style') || '';
                        const m = style.match(/background-image:\s*url\(['\"]?([^'\")]+)['\"]?\)/);
                        if (m) image = m[1];
                    }
                    const img = card.querySelector('img');
                    let title = '';
                    if (img) {
                        title = img.getAttribute('alt') || img.getAttribute('title') || '';
                        if (!image) image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    }
                    if (!title) {
                        title = (card.textContent || '').trim().split('\n')[0].trim();
                    }
                    let pt = '';
                    const ptSpan = card.querySelector('span.text-base');
                    if (ptSpan) {
                        pt = ptSpan.textContent.replace(/,/g, '').trim();
                    }
                    results.push({ title, image, url: a.href, pt });
                });
                return results;
            }
            """
        )

        for item in items:
            detail_url = item.get('url', '').strip()
            if detail_url.startswith('/'):
                detail_url = urljoin(BASE_URL, detail_url)
            if not detail_url or detail_url in existing_urls:
                continue

            image_url = item.get('image', '').strip()
            if image_url.startswith('/'):
                image_url = urljoin(BASE_URL, image_url)

            title = item.get('title', 'noname').strip() or 'noname'
            pt_text = item.get('pt', '').strip()

            rows.append([title, image_url, detail_url, pt_text])
            existing_urls.add(detail_url)
        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if not rows:
        print('📭 新規データなし')
        return
    try:
        sheet.append_rows(rows, value_input_option='USER_ENTERED')
        print(f'📥 {len(rows)} 件追記完了')
    except Exception as exc:
        print(f'❌ スプレッドシート書き込み失敗: {exc}')


if __name__ == '__main__':
    main()
