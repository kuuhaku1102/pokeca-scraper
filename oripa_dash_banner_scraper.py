import os
import base64
from urllib.parse import urljoin


import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa-dash.com/user/packList"

import requests
import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

BASE_URL = "https://oripa-dash.com"
TARGET_URL = "https://oripa-dash.com/user/packList"

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
    urls = set()
    for row in records[1:]:
        if len(row) >= 1:
            urls.add(row[0].strip())
    return urls


def scrape_banners(existing_urls: set):

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 oripa-dash.com スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector(".swiper-slide", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("oripa_dash_banner_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        slides = page.query_selector_all(".swiper-slide")
        for slide in slides:
            img = slide.query_selector("img")
            if not img:
                continue
            src = (img.get_attribute("src") or "").strip()
            if not src:
                continue
            if src.startswith("/"):
                src = urljoin(BASE_URL, src)

            link = slide.query_selector("a")
            href = (link.get_attribute("href") if link else "").strip()
            if href.startswith("/"):
                href = urljoin(BASE_URL, href)

            if src not in existing_urls:
                rows.append([src, href or BASE_URL])
                existing_urls.add(src)
        browser.close()
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print(f"🛑 ページ取得失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    slides = soup.select(".swiper-wrapper .swiper-slide")

    rows = []
    for slide in slides:
        a_tag = slide.find("a")
        img_tag = slide.find("img")
        if not a_tag or not img_tag:
            continue

        link_url = urljoin(BASE_URL, a_tag.get("href", ""))
        img_src = urljoin(BASE_URL, img_tag.get("src", "") or "")

        if img_src and img_src not in existing_urls:
            rows.append([img_src, link_url])
            existing_urls.add(img_src)

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
