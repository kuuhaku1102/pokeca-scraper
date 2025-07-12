import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://tora.net-oripa.com/"
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
            urls.add(row[2].strip())
    return urls

def parse_items(page) -> List[dict]:
    return page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('section.overflow-hidden').forEach(sec => {
                const a = sec.querySelector('a[href]');
                if (!a) return;
                let url = a.getAttribute('href') || '';
                let image = '';
                const img = sec.querySelector('img');
                if (img) {
                    const srcset = img.getAttribute('srcset');
                    if (srcset) {
                        const parts = srcset.split(',').map(p => p.trim().split(' ')[0]);
                        if (parts.length) image = parts[parts.length - 1];
                    } else {
                        image = img.getAttribute('src') || '';
                    }
                }
                let title = '';
                const titleEl = sec.querySelector('h2, h3, p.font-bold, span.font-bold');
                if (titleEl) {
                    title = titleEl.textContent.trim();
                } else if (img) {
                    title = img.getAttribute('alt') || '';
                }
                const ptEl = sec.querySelector('span.text-xl.font-bold, span.font-semibold');
                const pt = ptEl ? ptEl.textContent.replace(/[^0-9]/g, '') : '';
                results.push({title, image, url, pt});
            });
            return results;
        }
    """)

def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    debug_html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print('🔍 tora.net-oripa.com スクレイピング開始...')
        try:
            page.goto(BASE_URL, timeout=60000, wait_until='networkidle')
            page.wait_for_selector('section.overflow-hidden', timeout=60000)
        except Exception as exc:
            print(f'🛑 ページ読み込み失敗: {exc}')
            debug_html = page.content()
            browser.close()
            with open('tora_net_oripa_debug.html', 'w', encoding='utf-8') as f:
                f.write(debug_html)
            return rows
        items = parse_items(page)
        debug_html = page.content()
        browser.close()
    for item in items:
        detail_url = item.get('url', '').strip()
        image_url = item.get('image', '').strip()
        title = item.get('title', 'noname').strip() or 'noname'
        pt_text = item.get('pt', '').strip()
        if detail_url.startswith('/'):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith('/'):
            image_url = urljoin(BASE_URL, image_url)
        if detail_url in existing_urls:
            print(f'⏭ スキップ（重複）: {title}')
            continue
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)
    with open('tora_net_oripa_debug.html', 'w', encoding='utf-8') as f:
        f.write(debug_html)
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
