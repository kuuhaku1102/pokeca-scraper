import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ================================================================
# torenet.com pack list scraper
#   - Scrapes pack information from https://torenet.com/user/packList
#   - Appends new rows [title, image_url, detail_url, pt] to Google Sheets
#   - Google Sheets credentials are provided via GSHEET_JSON env (base64)
#   - Target sheet name: "その他" ("Others")
# ================================================================

BASE_URL = "https://torenet.com/user/packList"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


def save_credentials() -> str:
    """Decode GSHEET_JSON and write to a credentials file."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return worksheet object for the target spreadsheet."""
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
    """Read existing URLs (3rd column) from the sheet."""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def scrape_torenet(existing_urls: set) -> List[List[str]]:
    """Scrape torenet pack list page and return new rows."""
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 torenet.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_selector(".packList__item", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("torenet_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('.packList__item').forEach(item => {
                    const attrTitle = item.getAttribute('data-pack-name') || '';
                    const titleEl = item.querySelector('.packList__name');
                    const title = attrTitle || (titleEl ? titleEl.textContent.trim() : '');
                    const img = item.querySelector('img');
                    let image = '';
                    if (img) {
                        image = img.getAttribute('src') || '';
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            const parts = srcset.split(',').map(p => p.trim().split(' ')[0]);
                            if (parts.length) image = parts[parts.length - 1];
                        }
                    }
                    const packId = item.getAttribute('data-pack-id');
                    const packName = item.getAttribute('data-pack-name');
                    let url = '';
                    if (packId) {
                        url = `/pack/${packId}`;
                    } else if (packName) {
                        url = `/pack/${packName}`;
                    }
                    const ptEl = item.querySelector('.packList__price, .packList__pt-txt, [class*="pt"]');
                    let pt = '';
                    if (ptEl) {
                        const text = ptEl.textContent.replace(/\s+/g, '');
                        const m = text.match(/(\d+)/);
                        if (m) pt = m[1];
                    }
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
        pt_text = item.get("pt", "")

        if detail_url.startswith("/"):
            detail_url = urljoin("https://torenet.com", detail_url)
        if image_url.startswith("/"):
            image_url = urljoin("https://torenet.com", image_url)

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        print(f"✅ 取得: {title}")
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)

    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_torenet(existing_urls)
    print(f"rows（新規データ）: {rows}")
    if not rows:
        print("📭 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    except Exception as exc:
        print(f"❌ 書き込みエラー: {exc}")


if __name__ == "__main__":
    main()
