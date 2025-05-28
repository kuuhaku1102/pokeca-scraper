import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://dorima8.com/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


def save_credentials() -> str:
    """GSHEET_JSON環境変数から認証ファイルを保存"""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """スプレッドシートのシートオブジェクトを取得"""
    creds_path = save_credentials()
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    if not SPREADSHEET_URL:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_existing_urls(sheet) -> set:
    """既存のURL一覧を取得しセット化"""
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            urls.add(row[2].strip())
    return urls


def parse_items(page) -> List[dict]:
    """現在のページからアイテム情報を抽出"""
    items = page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.banner_base.banner').forEach(box => {
                const titleEl = box.querySelector('.name_area-pack_name');
                const imgEl = box.querySelector('.image_area img.current');
                const ptEl = box.querySelector('.point_area');
                const linkEl = box.querySelector('a[href]');

                const title = titleEl ? titleEl.textContent.trim() : 'noname';
                const image = imgEl ? imgEl.getAttribute('src') || '' : '';
                const url = linkEl ? linkEl.getAttribute('href') || '' : '';
                let pt = '';
                if (ptEl) {
                    const m = ptEl.textContent.replace(/,/g, '').match(/(\d+)/);
                    if (m) pt = m[1];
                }
                results.push({ title, image, url, pt });
            });
            return results;
        }
        """
    )
    return items


def fetch_items(existing_urls: set) -> List[List[str]]:
    """ページを巡回して新規アイテムを収集"""
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        next_url = BASE_URL
        visited = set()
        while next_url and next_url not in visited:
            visited.add(next_url)
            try:
                page.goto(next_url, timeout=60000)
                page.wait_for_selector('div.banner_base.banner', timeout=60000)
            except Exception as exc:
                print(f"🛑 ページ読み込み失敗: {exc}")
                break

            items = parse_items(page)
            for item in items:
                detail_url = item.get("url", "").strip() or BASE_URL
                image_url = item.get("image", "").strip()
                title = item.get("title", "noname").strip() or "noname"
                pt_text = item.get("pt", "").strip()

                if detail_url.startswith('/'):
                    detail_url = urljoin(BASE_URL, detail_url)
                if image_url.startswith('/'):
                    image_url = urljoin(BASE_URL, image_url)

                if detail_url in existing_urls:
                    continue

                rows.append([title, image_url, detail_url, pt_text])
                existing_urls.add(detail_url)

            # 次ページを探す
            next_href = None
            selectors = ["a[rel='next']", "a.next", "a:has-text('次')", "a:has-text('>')"]
            for sel in selectors:
                try:
                    link = page.query_selector(sel)
                except Exception:
                    link = None
                if link:
                    href = link.get_attribute('href')
                    if href and not href.startswith('javascript'):
                        next_href = href
                        break
            if next_href:
                next_url = urljoin(BASE_URL, next_href)
            else:
                break

        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = fetch_items(existing_urls)
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
