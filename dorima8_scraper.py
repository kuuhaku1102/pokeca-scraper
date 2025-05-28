import os
import base64
import time
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


def wait_until_all_banners(page, min_count=5, max_wait=12):
    """バナーが安定して複数出現するまで待つ"""
    start = time.time()
    last_count = 0
    stable_count = 0
    while True:
        current_count = page.eval_on_selector_all('div.banner_base.banner', "els => els.length")
        if current_count == last_count and current_count >= min_count:
            stable_count += 1
        else:
            stable_count = 0
        last_count = current_count
        if stable_count >= 2:  # 2回連続で同じなら安定とみなす
            break
        if time.time() - start > max_wait:
            break
        time.sleep(0.7)
    return current_count


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
                const title = titleEl ? titleEl.textContent.trim() : 'noname';
                const image = imgEl ? imgEl.getAttribute('src') || '' : '';
                const url = window.location.pathname;  // 詳細ページURLがないためページのパス
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
        page.goto(BASE_URL, timeout=60000)
        # ページに十分なバナーが出揃うまで待機
        wait_until_all_banners(page, min_count=5, max_wait=15)
        items = parse_items(page)
        for item in items:
            detail_url = BASE_URL  # 詳細ページへの個別URLがないためTOPのURLを代用
            image_url = item.get("image", "").strip()
            title = item.get("title", "noname").strip() or "noname"
            pt_text = item.get("pt", "").strip()

            if image_url.startswith('/'):
                image_url = urljoin(BASE_URL, image_url)

            # 本来は詳細URLが一意識別になるが、ここでは画像URLで重複判定する
            check_key = image_url  # URLが固定の場合はimage_urlで一意性
            if check_key in existing_urls:
                continue

            rows.append([title, image_url, detail_url, pt_text])
            existing_urls.add(check_key)

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
