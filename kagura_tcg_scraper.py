import os
import base64
import re
from typing import List
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://cardel.online/"
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
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 cardel.online スクレイピング開始...")

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div[id$='-Wrap']", timeout=10000)

            # スクロールで要素をロード
            page.evaluate("""
                async () => {
                    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                    for (let i = 0; i < 30; i++) {
                        window.scrollBy(0, window.innerHeight);
                        await delay(300);
                    }
                }
            """)
            page.wait_for_timeout(1000)

            index = 0
            while True:
                elements = page.query_selector_all("div[id$='-Wrap']")
                if index >= len(elements):
                    break

                try:
                    el = elements[index]
                    title = el.get_attribute("title") or f"noname-{index}"

                    # 画像
                    image = ""
                    fig = el.query_selector("figure")
                    if fig:
                        img = fig.query_selector("img")
                        if img:
                            image = img.get_attribute("src")

                    # pt
                    pt_text = ""
                    pt_el = el.query_selector("div.flex.justify-end p.text-sm")
                    if pt_el:
                        pt_text = pt_el.inner_text().strip()
                    else:
                        m = re.search(r"([0-9,]+)\s*pt", el.inner_text())
                        if m:
                            pt_text = m.group(1)

                    # 遷移してURL取得
                    el.scroll_into_view_if_needed()
                    el.click(timeout=10000)
                    page.wait_for_timeout(2000)
                    detail_url = page.url
                    norm_url = normalize_url(detail_url)

                    if norm_url in existing_urls:
                        print(f"⏭ スキップ（重複）: {title}")
                        page.go_back(wait_until="networkidle")
                        page.wait_for_selector("div[id$='-Wrap']", timeout=10000)
                        page.wait_for_timeout(1000)
                        index += 1
                        continue

                    rows.append([title, image, detail_url, re.sub(r"[^0-9]", "", pt_text)])
                    existing_urls.add(norm_url)
                    print(f"✅ 取得: {title} - {detail_url}")

                    # 戻って再安定
                    page.go_back(wait_until="networkidle")
                    page.wait_for_selector("div[id$='-Wrap']", timeout=10000)
                    page.wait_for_timeout(1000)
                    index += 1

                except Exception as e:
                    print(f"⚠️ アイテム処理失敗: {e}")
                    page.go_back(wait_until="networkidle")
                    page.wait_for_selector("div[id$='-Wrap']", timeout=10000)
                    page.wait_for_timeout(1000)
                    index += 1

        except Exception as e:
            print("🛑 スクレイピング失敗:", e)

        browser.close()
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
