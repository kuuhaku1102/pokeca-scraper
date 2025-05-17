import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://japan-toreca.com/"
SHEET_NAME = "その他"


def save_credentials() -> str:
    """Decode credentials JSON from env and save to a file."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return gspread worksheet using env SPREADSHEET_URL."""
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = os.environ.get("SPREADSHEET_URL")
    if not sheet_url:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_existing_urls(sheet) -> set:
    """Get existing detail URLs from the sheet."""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def fetch_items(existing_urls: set) -> List[List[str]]:
    """Scrape TOP page of japan-toreca using Playwright."""
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 japan-toreca スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("img", timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            html = page.content()
            browser.close()
            with open("japan_toreca_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        # DOMから必要情報を抽出
        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('[data-sentry-source-file="NewOripaCard.tsx"]').forEach(card => {
                    const link = card.closest('a') || card.querySelector('a[href]');
                    const img = card.querySelector('img');
                    if (!link || !img) return;
                    const title = (img.getAttribute('alt') || '').trim() || 'noname';
                    let image = img.getAttribute('src') || '';
                    const srcset = img.getAttribute('srcset');
                    if (srcset) {
                        const parts = srcset.split(',').map(s => s.trim().split(' ')[0]);
                        image = parts[parts.length - 1] || image;
                    }
                    let pt = '';
                    const span = card.querySelector('p span');
                    if (span) pt = span.textContent.trim();
                    results.push({ title, image, url: link.href, pt });
                });
                return results;
            }
            """
        )
        html = page.content()
        browser.close()

    # 先頭10件程度のみ利用
    for item in items[:10]:
        detail_url = item.get("url", "")
        image_url = item.get("image", "")
        title = item.get("title", "") or "noname"
        pt_text = item.get("pt", "")

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        print(f"✅ 取得: {title}")
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)

    with open("japan_toreca_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = fetch_items(existing_urls)
    if not rows:
        print("📭 新規データなし")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 {len(rows)} 件追記完了")


if __name__ == "__main__":
    main()
