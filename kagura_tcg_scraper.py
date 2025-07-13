import os
import base64
import re
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://kagura-tcg.com/"
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


def strip_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            u = row[2].strip()
            if u:
                urls.add(strip_query(u))
    return urls


def parse_items(page):
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.rounded-lg.border-neutral-800').forEach(box => {
                let url = '';
                const link = box.closest('a[href]') || box.querySelector('a[href]');
                if (link) url = link.href;

                let image = '';
                const imgDiv = box.querySelector('div[style*="background-image"]');
                if (imgDiv) {
                    const m = imgDiv.style.backgroundImage.match(/url\\(["']?(.*?)["']?\\)/);
                    if (m) image = m[1];
                }

                let title = '';
                const badge = box.querySelector('div.absolute');
                if (badge) title = badge.textContent.trim();

                let pt = '';
                const ptEl = box.querySelector('span.text-base');
                if (ptEl) pt = ptEl.textContent.replace(/\\s+/g, '');

                results.push({ title, image, url, pt });
            });
            return results;
        }
        """
    )


def scrape_items(existing_urls: set) -> list:
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 kagura-tcg.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)  # JS描画待ち
            page.wait_for_selector('div.rounded-lg.border-neutral-800', timeout=30000)

            items = parse_items(page)
            print(f"📦 取得件数: {len(items)}")

        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            try:
                html = page.content()
                with open("kagura_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("💾 kagura_debug.html を保存しました")
            except Exception as e:
                print(f"⚠️ HTML保存失敗: {e}")
            return []

        finally:
            browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip() or "noname"
        pt_text = item.get("pt", "")
        pt_value = re.sub(r"[^0-9]", "", pt_text)

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = strip_query(detail_url)
        if norm_url in existing_urls:
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
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"📥 {len(rows)} 件追記完了")
        except Exception as exc:
            print(f"❌ スプレッドシート書き込み失敗: {exc}")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
