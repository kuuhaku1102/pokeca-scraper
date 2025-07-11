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
    seen_srcs = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            print("⏳ ページ読み込み完了、スライド移動開始...")
            page.wait_for_timeout(3000)

            # スライド要素と幅を取得
            info = page.evaluate("""
                () => {
                    const slides = document.querySelectorAll('[aria-roledescription="slide"]');
                    const container = document.querySelector('.overflow-hidden .flex');
                    const slideWidth = slides[0]?.offsetWidth || 320;
                    return { count: slides.length, width: slideWidth };
                }
            """)

            total = info["count"]
            width = info["width"]
            print(f"🎞️ スライド枚数: {total}, 1枚あたり幅: {width}px")

            for i in range(total):
                page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('.overflow-hidden .flex');
                        if (el) {{
                            el.style.transform = "translate3d(-{width * i}px, 0px, 0px)";
                        }}
                    }}
                """)
                page.wait_for_timeout(800)

                # 現在表示中のスライド画像を取得
                banners = page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('[aria-roledescription="slide"] img')).map(img => {
                            const srcset = img.getAttribute('srcset');
                            let src = null;
                            if (srcset) {
                                src = srcset.split(',')[0].split(' ')[0].trim(); // 1x
                            } else {
                                src = img.getAttribute('src');
                            }
                            const href = img.closest('a')?.href || null;
                            return { src, href };
                        });
                    }
                """)

                for banner in banners:
                    src = banner["src"]
                    href = banner["href"] or BASE_URL
                    if not src or src in seen_srcs or src in existing_urls:
                        continue
                    full_src = urljoin(BASE_URL, src)
                    full_href = urljoin(BASE_URL, href)
                    rows.append([full_src, full_href])
                    seen_srcs.add(src)

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
