import os
import base64
import time
import re
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# Base settings
BASE_URL = "https://iris-toreca.com/"
PACK_SELECTOR = "a.pack-content"  # selector for each pack link
THUMBNAIL_SELECTOR = "div.pack-thumbnail img"  # image element inside a.pack-content
PRICE_SELECTOR = "div.pack-price-count i"  # element containing PT text
TITLE_SELECTOR = "h1"  # title element on detail page

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def save_credentials() -> str:
    """Decode service account json from env and save to file."""
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
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_pt(text: str) -> str:
    match = re.search(r"(\d+(?:,\d+)*)", text)
    return match.group(1) if match else ""


def fetch_title(detail_url: str) -> str:
    time.sleep(1)  # be polite
    try:
        soup = fetch_page(detail_url)
    except Exception as exc:
        print(f"⚠ Failed to load detail page: {detail_url} ({exc})")
        return ""
    title_tag = soup.select_one(TITLE_SELECTOR)
    if title_tag:
        return title_tag.get_text(strip=True)
    if soup.title:
        return soup.title.get_text(strip=True)
    return ""


def scrape() -> List[List[str]]:
    print("🔍 Fetching list page…")
    soup = fetch_page(BASE_URL)
    results = []
    for a in soup.select(PACK_SELECTOR):
        img_tag = a.select_one(THUMBNAIL_SELECTOR)
        pt_tag = a.select_one(PRICE_SELECTOR)
        image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
        detail_url = a.get("href", "")
        pt_text = pt_tag.get_text(strip=True) if pt_tag else ""

        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        pt_value = extract_pt(pt_text)
        title = fetch_title(detail_url) if detail_url else ""

        results.append([title, image_url, detail_url, pt_value])
    return results


def main():
    sheet = get_sheet()
    rows = scrape()
    if not rows:
        print("📭 No data scraped")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} rows")


if __name__ == "__main__":
    main()
