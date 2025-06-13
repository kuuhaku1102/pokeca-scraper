import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://grim-tcg.net-oripa.com/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")

GACHA_SECTION_SELECTOR = "section.rounded-xl"


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
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set


def extract_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("\U0001F50D grim-tcg.net-oripa.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector(GACHA_SECTION_SELECTOR, timeout=60000)
        except Exception as exc:
            print(f"\U0001F6D1 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("grim_oripa_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        sections = page.query_selector_all(GACHA_SECTION_SELECTOR)
        print(f"検出されたセクション数: {len(sections)}")
        for sec in sections:
            try:
                link = sec.query_selector("a[href]")
                if not link:
                    continue
                detail_url = link.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()
                if not detail_url or detail_url in existing_urls:
                    continue

                img = link.query_selector("img") or sec.query_selector("img")
                image_url = ""
                title = "noname"
                if img:
                    image_url = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or ""
                    ).strip()
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                    alt = img.get_attribute("alt") or img.get_attribute("title")
                    if alt:
                        alt = alt.strip()
                        if not re.match(r"^https?://", alt):
                            title = alt or title
                if title == "noname":
                    text = sec.inner_text().strip()
                    if text:
                        title = text.splitlines()[0]

                pt_value = ""
                pt_candidates = sec.query_selector_all("span.font-bold")
                for pt_el in pt_candidates:
                    t = pt_el.inner_text().replace(",", "")
                    m = re.search(r"(\d{2,6})", t)
                    if m:
                        pt_value = m.group(1)
                        break

                rows.append([title, image_url, detail_url, pt_value])
                existing_urls.add(detail_url)
            except Exception as exc:
                print(f"⚠ 取得スキップ: {exc}")
                continue
        browser.close()
    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = extract_items(existing_urls)
    if not rows:
        print("\U0001F4E5 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"\U0001F4E4 {len(rows)} 件追記完了")
    except Exception as exc:
        print(f"❌ スプレッドシート書き込み失敗: {exc}")


if __name__ == "__main__":
    main()
