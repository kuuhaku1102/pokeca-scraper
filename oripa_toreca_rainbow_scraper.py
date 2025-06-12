import os
import base64
import re
from urllib.parse import urljoin
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa.toreca-rainbow.com/"
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


def scroll_to_bottom(page, max_scrolls: int = 20, pause_ms: int = 500) -> None:
    """Scroll page to the bottom to ensure lazy content is loaded."""
    last_height = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        height = page.evaluate("document.body.scrollHeight")
        if height == last_height:
            break
        last_height = height


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        print("🔍 oripa.toreca-rainbow.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector("a[href^='/pack/']", timeout=60000)
            scroll_to_bottom(page)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("toreca_rainbow_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll("a[href^='/pack/']").forEach(a => {
                    const img = a.querySelector('img');
                    const title = img ? (img.alt || '').trim() : '';
                    const image = img ? (img.src || '').trim() : '';
                    const url = a.href;
                    let pt = '';
                    const nextDiv = a.parentElement ? a.parentElement.nextElementSibling : null;
                    if (nextDiv) {
                        const span = nextDiv.querySelector('div.bg-gradient-silver span.text-sm.font-bold');
                        if (span) pt = span.textContent.trim();
                    }
                    results.push({title, image, url, pt});
                });
                return results;
            }
            """
        )
        browser.close()

    for item in items:
        detail_url = item.get("url", "")
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        image_url = item.get("image", "")
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)
        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "")
        pt_value = re.sub(r"[^0-9]", "", pt_text)
        if not detail_url or detail_url in existing_urls:
            continue
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
