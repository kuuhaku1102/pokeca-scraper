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
        if len(row) >= 2:
            u = row[1].strip()
            if u:
                urls.add(strip_query(u))
    return urls


def scrape_items(existing_urls: set) -> list:
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 kagura-tcg.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            cards = page.query_selector_all("div.flex.flex-col.cursor-pointer")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            try:
                html = page.content()
                with open("kagura_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("💾 kagura_debug.html を保存しました")
            except Exception as e:
                print(f"⚠️ HTML保存失敗: {e}")
            browser.close()
            return rows

        print(f"📦 取得件数: {len(cards)}")

        for i in range(len(cards)):
            try:
                cards = page.query_selector_all("div.flex.flex-col.cursor-pointer")
                card = cards[i]

                # background-image から画像URL取得
                try:
                    img_div = card.query_selector("div[style*='background-image']")
                    style = img_div.get_attribute("style")
                    match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
                    image_url = match.group(1) if match else ""
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                except:
                    image_url = ""

                with page.expect_navigation(wait_until="load", timeout=30000):
                    card.click()

                detail_url = page.url
                norm_url = strip_query(detail_url)
                if not norm_url:
                    print("⚠️ URLが空のためスキップ")
                    page.go_back()
                    page.wait_for_timeout(1000)
                    page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)
                    continue
                if norm_url in existing_urls:
                    print(f"⏭ スキップ（重複）: {norm_url}")
                    page.go_back()
                    page.wait_for_timeout(1000)
                    page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)
                    continue

                try:
                    title = page.query_selector("h1").inner_text().strip()
                except:
                    title = "noname"

                try:
                    pt_el = page.query_selector(".fa-coins")
                    pt_text = pt_el.evaluate("el => el.parentElement.textContent")
                    pt_value = re.sub(r"[^0-9]", "", pt_text)
                except:
                    pt_value = ""

                rows.append([title, image_url, detail_url, pt_value])
                existing_urls.add(norm_url)

                page.go_back()
                page.wait_for_timeout(1000)
                page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)

            except Exception as e:
                print(f"⚠️ アイテム処理失敗: {e}")
                try:
                    page.go_back()
                    page.wait_for_timeout(1000)
                    page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)
                except:
                    pass

        browser.close()
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
