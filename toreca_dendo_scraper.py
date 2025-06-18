import os
import base64
import re
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.toreca-dendo.com/"
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
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def scrape_items(existing_urls: set):
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 toreca-dendo スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.product-container img", timeout=60000)
        except Exception as exc:
            html = page.content()
            with open("toreca_dendo_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            print(f"🛑 ページ読み込み失敗: {exc}")
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.product-container.flex.flex-col.p-2').forEach(box => {
                    const root = box.parentElement;
                    const img = root ? root.querySelector('img') : null;
                    if (!img) return;
                    const title = (img.getAttribute('alt') || img.getAttribute('title') || '').trim();
                    const image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    const ptEl = box.querySelector('span.vc_module__point-raw--value');
                    const pt = ptEl ? ptEl.textContent.trim() : '';
                    let code = '';
                    const m = image.match(/\/products\/p\/(.*?)\//);
                    if (m) code = m[1];
                    const url = code ? `/products/p/${code}` : '';
                    results.push({ title, image, url, pt });
                });
                return results;
            }
            """
        )
        browser.close()

    for item in items:
        detail_url = item.get("url", "")
        image_url = item.get("image", "")
        title = item.get("title", "").strip() or "noname"
        pt_text = re.sub(r"[^0-9]", "", item.get("pt", ""))

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


def main():
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
