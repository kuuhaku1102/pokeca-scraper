import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://torecatokyo.com"
# Listing may appear on top page or /gacha/ depending on the site state
# so attempt both URLs.
TARGET_URLS = [
    "https://torecatokyo.com/",
    "https://torecatokyo.com/gacha/",
]
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


def normalize_url(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def parse_items(page) -> List[dict]:
    js = """
    () => {
        const results = [];
        document.querySelectorAll('li.gacha_list_card').forEach(li => {
            const a = li.querySelector('a.gacha_eyecatch');
            const url = a ? a.href : '';
            let image = '';
            let title = '';
            if (a) {
                const img = a.querySelector('img');
                if (img) {
                    image = img.getAttribute('src') || '';
                    title = img.getAttribute('alt') || '';
                }
            }
            const ptEl = li.querySelector('.gacha_list_mater_points strong');
            const pt = ptEl ? ptEl.textContent.trim() : '';
            results.push({ title, image, url, pt });
        });
        return results;
    }
    """
    return page.evaluate(js)


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9"},
        )
        page = context.new_page()
        print("🔍 torecatokyo.com スクレイピング開始...")
        success = False
        for url in TARGET_URLS:
            try:
                response = page.goto(url, timeout=120000, wait_until="networkidle")
                if response and not response.ok:
                    raise RuntimeError(f"HTTP {response.status}")
                page.wait_for_selector("li.gacha_list_card", timeout=120000)
                success = True
                break
            except Exception as exc:
                print(f"⚠️ {url} の読み込み失敗: {exc}")
        if not success:
            print("🛑 ページ読み込み失敗: すべてのURLで要素取得に失敗")
            html = page.content()
            with open("torecatokyo_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            context.close()
            browser.close()
            return rows

        items = parse_items(page)
        context.close()
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "")
        pt_value = re.sub(r"[^0-9]", "", pt_text)

        if detail_url.startswith('/'):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith('/'):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = normalize_url(detail_url)
        if not detail_url or norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_value])
        existing_urls.add(norm_url)

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
