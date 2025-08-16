import os
import base64
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://orikuji.com/"
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

def fetch_existing_url_paths(sheet) -> set:
    """シート内のURLカラムを 'パス部分だけ' でset化"""
    records = sheet.get_all_values()
    paths = set()
    for row in records[1:]:
        if len(row) >= 3:
            u = row[2].strip()
            if u:
                parsed = urlparse(u)
                paths.add(parsed.path)
    return paths

def scrape_orikuji(existing_paths: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 orikuji.com スクレイピング開始...")

        try:
            # The site continuously opens network connections which prevents
            # Playwright from reaching a "networkidle" state and results in a
            # timeout. Waiting for the DOM content instead is sufficient for
            # scraping the required elements.
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")

            # Scroll to the bottom repeatedly so that the site loads all
            # available gacha boxes (the page uses infinite scroll).
            def scroll_to_bottom(page, selector="div.white-box", max_scrolls=50, pause_ms=500):
                last_count = 0
                for _ in range(max_scrolls):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(pause_ms)
                    try:
                        load_more = page.query_selector("button:has-text('もっと見る')")
                        if load_more:
                            load_more.click()
                            page.wait_for_timeout(pause_ms)
                    except Exception:
                        pass
                    curr_count = len(page.query_selector_all(selector))
                    if curr_count <= last_count:
                        break
                    last_count = curr_count
                print(f"👀 {last_count}件の {selector} を検出")

            scroll_to_bottom(page)

            page.wait_for_selector("div.white-box img", timeout=60000)

            items = page.evaluate(
                """
                () => {
                    const results = [];
                    document.querySelectorAll('div.white-box').forEach(box => {
                        const link = box.querySelector('a[href*="/gacha/"]');
                        const img = box.querySelector('div.image-container img');
                        if (!link || !img) return;
                        const imgSrc = img.getAttribute('data-src') || img.getAttribute('src') || '';
                        if (
                            imgSrc.includes('/img/coin.png') ||
                            imgSrc.includes('/coin/lb_coin_')
                        ) return;

                        const title = img.getAttribute('alt') || 'noname';
                        const image = imgSrc;
                        const url = link.getAttribute('href') || '';
                        const ptEl = box.querySelector('span.coin-area');
                        const rawPt = ptEl ? ptEl.textContent : '';
                        const pt = rawPt.replace(/\D/g, '');
                        results.push({ title, image, url, pt });
                    });
                    return results;
                }
                """
            )
            print(f"取得したitems件数: {len(items)}")
            for item in items:
                print(f"item url: {item.get('url', '')}")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows
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

        path = urlparse(detail_url).path
        print(f"追加判定: {title} | path: {path} | 重複: {path in existing_paths}")
        if path in existing_paths:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_text])
        existing_paths.add(path)

    return rows

def main() -> None:
    sheet = get_sheet()
    existing_paths = fetch_existing_url_paths(sheet)
    rows = scrape_orikuji(existing_paths)
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
