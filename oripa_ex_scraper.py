import os
import base64
import time
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa.ex-toreca.com/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
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
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)

def fetch_items_playwright() -> List[List[str]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 JSレンダリング後のページにアクセス...")
        page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
        page.wait_for_selector("div.group.relative.cursor-pointer.rounded", timeout=10000)
        # JSで必要情報を抽出
        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.group.relative.cursor-pointer.rounded').forEach(box => {
                    const img = box.querySelector('img');
                    const title = img ? (img.getAttribute('alt') || '').trim() : '';
                    const safe_title = title ? title : 'noname';
                    const image = img ? img.getAttribute('src') : '';
                    let pt = '';
                    const ptEl = box.querySelector('p span');
                    if (ptEl) pt = ptEl.textContent.trim();
                    results.push([safe_title, image, pt]);
                });
                return results;
            }
            """
        )
        browser.close()
        return items

def main():
    sheet = get_sheet()
    existing_data = sheet.get_all_values()[1:]
    existing_titles = set(row[0].strip() for row in existing_data if row and len(row) > 0)
    print(f"✅ 既存データ {len(existing_titles)} 件")
    items = fetch_items_playwright()
    if not items:
        print("📭 No data scraped")
        return

    # 新規のみ抽出（タイトル一致で判定）
    new_rows = [row for row in items if row[0] not in existing_titles]
    print(f"🆕 新規 {len(new_rows)} 件")

    if new_rows:
        sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(new_rows)} 件追記完了")
    else:
        print("📭 新規データなし")

if __name__ == "__main__":
    main()
