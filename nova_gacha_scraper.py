import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.novagacha.com"
TARGET_URL = "https://www.novagacha.com/?tab=gacha&category=2"
SHEET_NAME = "その他"
MAX_CELLS = 10_000_000


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
    return spreadsheet, spreadsheet.worksheet(SHEET_NAME)


def can_append(spreadsheet, additional_cells: int) -> bool:
    meta = spreadsheet.fetch_sheet_metadata()
    total_cells = 0
    for sheet in meta.get("sheets", []):
        grid = sheet.get("properties", {}).get("gridProperties", {})
        rows = grid.get("rowCount", 0)
        cols = grid.get("columnCount", 0)
        total_cells += rows * cols

    if total_cells + additional_cells > MAX_CELLS:
        print(
            f"🛑 追加 {additional_cells} セルで上限 {MAX_CELLS} を超えるためスキップします "
            f"(現在のグリッドセル総数: {total_cells})"
        )
        return False

    return True


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
        document.querySelectorAll('section.flex.flex-col.px-1').forEach(sec => {
            const link = sec.querySelector('a[href]');
            if (!link) return;

            const url = link.href;

            // 画像URL
            let image = '';
            const bgDiv = sec.querySelector("div.bg-cover");
            if (bgDiv) {
                const match = /url\\(["']?(.*?)["']?\\)/.exec(bgDiv.style.backgroundImage);
                if (match) image = match[1];
            }

            // ポイント
            let pt = '';
            const ptEl = sec.querySelector("div.text-xl");
            if (ptEl) pt = ptEl.textContent.trim();

            // タイトル（現状HTMLにないため固定値）
            const title = "noname";

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
        page = browser.new_page()
        print("🔍 novagacha.com スクレイピング開始...")
        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('section.flex.flex-col.px-1', timeout=60000)
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
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = normalize_url(detail_url)
        if not detail_url or norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_value])
        existing_urls.add(norm_url)

    return rows


def main() -> None:
    spreadsheet, sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if rows:
        col_count = max(sheet.col_count, len(rows[0])) if rows else sheet.col_count
        additional_cells = len(rows) * col_count
        if can_append(spreadsheet, additional_cells):
            try:
                sheet.append_rows(rows, value_input_option="USER_ENTERED")
                print(f"📥 {len(rows)} 件追記完了")
            except gspread.exceptions.APIError as exc:
                print(f"🛑 追記失敗: {exc}")
        else:
            print("📭 シート上限のため書き込みを見送りました")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
