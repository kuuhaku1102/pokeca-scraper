import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# Set a desktop Chrome user agent to avoid simple bot blocking
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://torekazi.com/"
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


def parse_items(page) -> List[dict]:
    """Return list of item dicts from the currently loaded page."""
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.bg-white.rounded-lg').forEach(card => {
                const a = card.querySelector('a[href]');
                if (!a) return;
                const img = a.querySelector('img');
                const url = a.href;
                const image = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                const titleEl = card.querySelector('h2, h3, p.font-semibold, p.font-bold');
                let title = titleEl ? titleEl.textContent.trim() : '';
                if (!title && img) {
                    title = img.getAttribute('alt') || '';
                }
                const ptEl = card.querySelector('div.flex p.font-bold.text-lg');
                const pt = ptEl ? ptEl.textContent.replace(/\s+/g, '') : '';
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
        page = browser.new_page(user_agent=DEFAULT_UA)
        print("🔍 torekazi.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.bg-white.rounded-lg', timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("torekazi_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = parse_items(page)
        browser.close()

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
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)
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
