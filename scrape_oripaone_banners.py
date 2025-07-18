import os
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripaone.jp"
TARGET_URL = BASE_URL
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
SHEET_NAME = "oripaone"


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


def fetch_with_requests() -> list[str]:
    # フォールバック用のシンプルなリクエスト関数（実装省略可）
    return []


def fetch_with_playwright() -> list[str]:
    """旧実装の置き換えラッパー"""
    return fetch_with_playwright_new()


def fetch_with_playwright_new() -> list[str]:
    """Playwrightを使用して、全スライドバナーを取得する"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(BASE_URL, timeout=60000)

        # スライドを強制読み込み
        page.wait_for_selector("div[aria-roledescription='slide'] img", timeout=60000)
        page.wait_for_timeout(3000)

        try:
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)
        except:
            pass

        img_elements = page.query_selector_all("div[aria-roledescription='slide'] img")
        urls: list[str] = []
        for img in img_elements:
            srcset = img.get_attribute("srcset")
            if srcset:
                src = srcset.split(" ")[0]
                if src not in urls:
                    urls.append(src)

        context.close()
        browser.close()
        return urls


def scrape_banners(existing_urls: set):
    urls = fetch_with_requests()
    if not urls:
        urls = fetch_with_playwright_new()

    rows = []
    if not urls:
        return rows

    for url in urls:
        full_url = urljoin(BASE_URL, url) if url.startswith("/") else url
        if full_url not in existing_urls:
            rows.append([full_url, TARGET_URL])
            existing_urls.add(full_url)
    return rows


def main():
    sheet = get_sheet()
    existing_urls = set()
    records = sheet.get_all_values()
    for row in records[1:]:
        if len(row) >= 1:
            existing_urls.add(row[0])

    rows = scrape_banners(existing_urls)
    if rows:
        sheet.append_rows(rows, value_input_option="RAW")
        print(f"✅ {len(rows)} 件追加しました")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
