import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.novagacha.com/?tab=gacha&category=2"
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
    # CSS class names contain a colon and slash which must be escaped twice in
    # the JavaScript string (\\ -> \) so that the selector passed to
    # querySelectorAll contains the correct backslash escaping.
    selector = "div.w-full.md\\:w-1\\/2 section"
    js = f"""
        () => {{
            const results = [];
            document.querySelectorAll('{selector}').forEach(sec => {{
                const link = sec.querySelector('a[href]');
                if (!link) return;
                const url = link.href;
                let image = '';
                const bg = link.querySelector("div[style*='background-image']");
                if (bg) {{
                    const m = /url\\(("|'|)(.*?)\1\\)/.exec(bg.style.backgroundImage);
                    if (m) image = m[2];
                }}
                let title = '';
                const t = sec.querySelector('h3, h2, .font-bold');
                if (t) title = t.textContent.trim();
                let pt = '';
                const ptEl = sec.querySelector('div.text-xl');
                if (ptEl) pt = ptEl.textContent.trim();
                results.push({{title, image, url, pt}});
            }});
            return results;
        }}
    """
    return page.evaluate(js)


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 novagacha.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.w-full.md\:w-1\/2 section', timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open('novagacha_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            browser.close()
            return rows

        items = parse_items(page)
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "")
        pt_value = re.sub(r"[^0-9]", "", pt_text)

        if detail_url.startswith("/"):
            detail_url = urljoin("https://www.novagacha.com", detail_url)
        if image_url.startswith("/"):
            image_url = urljoin("https://www.novagacha.com", image_url)

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
