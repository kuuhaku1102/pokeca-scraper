import os
import base64
from urllib.parse import urljoin
from typing import List
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://kagura-tcg.com/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON is missing")
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
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    return {row[2] for row in records[1:] if len(row) >= 3 and row[2].strip()}


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)
        except Exception as e:
            html = page.content()
            with open("kagura_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"🛑 セレクタ待機失敗: {e}")
            browser.close()
            return []

        cards = page.query_selector_all("a[href*='/gacha/']")
        for a in cards:
            card = a.query_selector("div.flex.flex-col.cursor-pointer") or a
            if not card:
                continue

            # 画像取得
            image_url = ""
            bg = card.query_selector("div[style*='background-image']")
            if bg:
                style = bg.get_attribute("style") or ""
                if "url(" in style:
                    raw = style.split("url(")[-1].split(")")[0].strip("\"'")
                    image_url = urljoin(BASE_URL, raw)

            # タイトル取得
            title = card.inner_text().split("\n")[0].strip() or "noname"

            # PT取得
            pt = ""
            pt_span = card.query_selector("span.text-base")
            if pt_span:
                pt = pt_span.inner_text().replace(",", "").strip()

            # URL取得
            detail_url = a.get_attribute("href")
            if detail_url:
                detail_url = urljoin(BASE_URL, detail_url.strip())

            # 重複スキップ
            if not detail_url or detail_url in existing_urls:
                continue

            rows.append([title, image_url, detail_url, pt])
            existing_urls.add(detail_url)

        browser.close()
    return rows


def main():
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if not rows:
        print("📭 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")


if __name__ == "__main__":
    main()
