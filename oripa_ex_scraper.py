import os
import base64
import time
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# Base configuration
BASE_URL = "https://oripa.ex-toreca.com/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"
HEADERS = {"User-Agent": "Mozilla/5.0"}

ITEM_SELECTOR = "div.group.relative.cursor-pointer.rounded"
IMG_SELECTOR = "img"
PT_SELECTOR = "p span"


def save_credentials() -> str:
    """Decode service account JSON from env and save to file."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    creds_path = save_credentials()
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def scrape() -> List[List[str]]:
    print("🔍 Fetching list page…")
    soup = fetch_page(BASE_URL)
    results: List[List[str]] = []

    for item in soup.select(ITEM_SELECTOR):
        img_tag = item.select_one(IMG_SELECTOR)
        pt_tag = item.select_one(PT_SELECTOR)
        a_tag = item.find_parent("a") or item.find("a")

        title = img_tag.get("alt", "") if img_tag else ""
        image_url = img_tag.get("src", "") if img_tag else ""
        pt_text = pt_tag.get_text(strip=True) if pt_tag else ""
        detail_url = a_tag.get("href", "") if a_tag else ""

        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)

        results.append([title, image_url, detail_url, pt_text])

    return results


def main():
    sheet = get_sheet()
    rows = scrape()
    if not rows:
        print("📭 No data scraped")
        return
    time.sleep(1)  # polite delay before writing
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} rows")


if __name__ == "__main__":
    main()
