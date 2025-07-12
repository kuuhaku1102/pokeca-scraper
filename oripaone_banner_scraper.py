import base64
import os
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripaone.jp"
TARGET_URL = BASE_URL
SHEET_NAME = "news"
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


def fetch_existing_image_urls(sheet) -> set:
    records = sheet.get_all_values()
    return set(row[0].strip() for row in records[1:] if row and row[0].strip())


def scrape_banners(existing_urls: set):
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # スライド切り替えボタン取得（例: .slick-next または .swiper-button-next）
            next_button = page.query_selector(".slick-next, .swiper-button-next")

            seen_srcs = set()
            for _ in range(15):  # 最大15回分スライドを巡回
                slides = page.query_selector_all("[aria-roledescription='slide']")
                for slide in slides:
                    img = slide.query_selector("img")
                    if not img:
                        continue
                    src = img.get_attribute("src")
                    if not src:
                        continue

                    full_src = urljoin(BASE_URL, src)
                    if full_src in seen_srcs or full_src in existing_urls:
                        continue

                    rows.append([full_src, BASE_URL])
                    seen_srcs.add(full_src)
                    existing_urls.add(full_src)

                # 次のスライドへ
                if next_button:
                    next_button.click()
                    page.wait_for_timeout(1000)  # 次のスライド読み込み待機

        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
        finally:
            browser.close()

    print(f"✅ {len(rows)} 件の新規バナー")
    return rows


def main() -> None:
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 新規データなし")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 {len(rows)} 件追記完了")


if __name__ == "__main__":
    main()
