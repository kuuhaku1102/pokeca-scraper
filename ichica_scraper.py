import os
import base64
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://ichica.co/"
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
    url_set = set()
    for row in records:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        # デバッグ時はheadless=Falseで可視化も
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        print("🔍 ichica.co スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=120000)  # wait_until省略
            # 雑に8秒待つ
            page.wait_for_timeout(8000)
            # タイムアウト値長めに
            page.wait_for_selector("div.bubble-element.group-item", timeout=120000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            browser.close()
            if html:
                with open("ichica_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
            return rows

        html = page.content()
        # デバッグ用に保存
        with open("ichica_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.bubble-element.group-item').forEach(card => {
                    const img = card.querySelector('img');
                    const image = img ? img.src : '';
                    const title = img ? (img.alt || img.title || '').trim() : '';
                    let url = '';
                    const a = card.querySelector('a[href]');
                    if (a) {
                        url = a.href;
                    } else {
                        const onclick = card.getAttribute('onclick');
                        const m = onclick && onclick.match(/window.open\\('([^']+)'/);
                        if (m) url = m[1];
                    }
                    const ptEl = card.querySelector('div.cmgaAy');
                    const pt = ptEl ? ptEl.textContent.trim() : '';
                    results.push({ title, image, url, pt });
                });
                return results;
            }
            """
        )
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname") or "noname"
        pt_value = item.get("pt", "").strip()

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = normalize_url(detail_url)
        if norm_url in existing_urls or not norm_url:
            continue

        rows.append([title, image_url, detail_url, pt_value])
        existing_urls.add(norm_url)

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
