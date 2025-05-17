import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://eve-gacha.com/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def save_credentials() -> str:
    """Decode credentials from env and write to file."""

def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return worksheet object for the target sheet."""
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
    """Fetch existing detail URLs to avoid duplicates."""
    records = sheet.get_all_values()
    url_set = set()
    # skip header row if present
    for row in (records[1:] if len(records) > 1 else []):
        if len(row) >= 3:
            url_set.add(row[2])
    return url_set


def extract_pt(text: str) -> str:
    """Return only digit characters from a text."""
    m = re.search(r"(\d+(?:,\d+)*)", text)
    return m.group(1) if m else ""


def fetch_items(existing_urls: set) -> List[List[str]]:
    """Scrape gacha info from eve-gacha.com."""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: List[List[str]] = []

    for a in soup.select("a[href*='/gacha/']"):
        detail_url = a.get("href", "")
        if not detail_url:
            continue
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if detail_url in existing_urls:
            continue

        img = a.find("img")
        image_url = ""
        title = "noname"
        if img:
            image_url = img.get("src", "")
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)
            alt = img.get("alt") or img.get("title")
            if alt:
                title = alt.strip() or title
        if not title or title == "noname":
            text = " ".join(t.strip() for t in a.stripped_strings if t.strip())
            if text:
                title = text

        pt_text = a.get_text(" ", strip=True)
        pt = extract_pt(pt_text)

        rows.append([title, image_url, detail_url, pt])
        existing_urls.add(detail_url)

    return rows


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:] if len(row) >= 3:
        url_set.add(row[2].strip())
    return url_set

def extract_pt(text: str) -> str:
    m = re.search(r"(\d{3,6})", text.replace(",", ""))
    return m.group(1) if m else ""

def fetch_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=60000)
        page.wait_for_timeout(3000)  # JSレンダリング待機（秒数は必要に応じて調整）

        # ここでaタグ選択
        cards = page.query_selector_all("a[href*='/gacha/']")
        print(f"取得したaタグ数: {len(cards)}")
        if len(cards) == 0:
            print("⚠️ Playwright経由でもaタグがゼロなら、セレクタ再調整やJS側の仕様変更を疑ってください")
        for a in cards:
            detail_url = a.get_attribute("href")
            if not detail_url:
                continue
            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            detail_url = detail_url.strip()
            if detail_url in existing_urls:
                continue
            # カードのimg/タイトル/PT等を抽出
            img = a.query_selector("img")
            image_url = ""
            title = "noname"
            if img:
                image_url = img.get_attribute("data-src") or img.get_attribute("src") or ""
                if image_url.startswith("/"):
                    image_url = urljoin(BASE_URL, image_url)
                image_url = image_url.strip()
                alt = img.get_attribute("alt") or img.get_attribute("title")
                if alt:
                    title = alt.strip() or title
            # タイトルが未取得ならa要素テキスト
            if title == "noname":
                text = a.inner_text().strip()
                if text:
                    title = text.split()[0]
            pt_text = a.inner_text().strip()
            pt = extract_pt(pt_text)
            rows.append([title, image_url, detail_url, pt])
            existing_urls.add(detail_url)
        browser.close()
    return rows

def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = fetch_items(existing_urls)
    if not rows:
        print("📭 No new data to append")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} new rows")

if __name__ == "__main__":
    main()
