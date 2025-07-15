import os
import base64
import re
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://torecaball.com/"
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
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                url_set.add(strip_query(url))
    return url_set


def scrape_items(existing_urls: set) -> list:
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 torecaball.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.Card_oripaContainer__D3x-F", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("torecaball_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        index = 0
        while True:
            cards = page.query_selector_all("div.Card_oripaContainer__D3x-F")
            if index >= len(cards):
                break
            card = cards[index]
            try:
                # 画像
                card.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                img = card.query_selector("div.Card_thumbnail__21WbN img") or card.query_selector("img")
                image_url = ""
                if img:
                    image_url = page.evaluate("el => el.src", img)
                    if not image_url:
                        image_url = img.get_attribute("data-src") or ""
                if image_url and image_url.startswith("/"):
                    image_url = urljoin(BASE_URL, image_url)

                # タイトル
                title_el = card.query_selector("p.Card_title__QiuTY")
                title = title_el.inner_text().strip() if title_el else "noname"

                # PT
                pt_el = card.query_selector("div.flex-align-center span.font-weight-bold")
                pt_text = pt_el.inner_text().strip() if pt_el else ""
                pt_value = re.sub(r"[^0-9]", "", pt_text)

                # URL
                a = card.query_selector("a[href]")
                detail_url = a.get_attribute("href") if a else ""
                if not detail_url:
                    with page.expect_navigation(wait_until="load", timeout=30000):
                        card.click()
                    detail_url = page.url
                    page.go_back(wait_until="load")
                    page.wait_for_selector("div.Card_oripaContainer__D3x-F", timeout=60000)
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)

                norm_url = strip_query(detail_url)
                if norm_url in existing_urls:
                    print(f"⏭ スキップ（重複）: {title}")
                    index += 1
                    continue

                rows.append([title, image_url, detail_url, pt_value])
                existing_urls.add(norm_url)
                print(f"✅ 取得: {title}")
                index += 1
            except Exception as exc:
                print(f"⚠️ エラー（スキップ）: {exc}")
                try:
                    page.go_back(wait_until="load")
                    page.wait_for_selector("div.Card_oripaContainer__D3x-F", timeout=60000)
                except Exception:
                    pass
                index += 1

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
