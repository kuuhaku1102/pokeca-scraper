import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://get-chance.net-oripa.com/"
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


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(url)
    return urls


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 get-chance スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("section.overflow-hidden", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("getchance_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        sections = page.query_selector_all("section.overflow-hidden")
        for sec in sections:
            try:
                a_tag = sec.query_selector("a[href]")
                if not a_tag:
                    continue
                detail_url = a_tag.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()
                if not detail_url or detail_url in existing_urls:
                    continue

                img = a_tag.query_selector("img")
                image_url = ""
                title = ""
                if img:
                    image_url = img.get_attribute("src") or img.get_attribute("data-src") or ""
                    title = img.get_attribute("alt") or ""
                if image_url.startswith("/"):
                    image_url = urljoin(BASE_URL, image_url)
                if not title:
                    title_el = sec.query_selector("h2") or sec.query_selector("h3") or sec.query_selector(".font-bold")
                    if title_el:
                        title = title_el.inner_text().strip()
                title = title.strip() or "noname"

                pt = ""
                pt_container = sec.query_selector("div.flex.items-center")
                if pt_container:
                    pt_spans = pt_container.query_selector_all("span.font-bold")
                    if len(pt_spans) >= 2:
                        pt = pt_spans[1].inner_text().strip()

                rows.append([title, image_url, detail_url, pt])
                existing_urls.add(detail_url)
            except Exception as exc:
                print(f"⚠ データ取得失敗: {exc}")
                continue
        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
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
