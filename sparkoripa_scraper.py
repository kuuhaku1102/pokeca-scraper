import os
import base64
from urllib.parse import urljoin
from typing import List

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

BASE_URL = "https://sparkoripa.jp/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def save_credentials() -> str:
    """Write service account json decoded from environment."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
    """Return gspread worksheet object."""
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)

def fetch_items() -> List[List[str]]:
    """Scrape gacha information from sparkoripa.jp, skipping coin/price images."""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: List[List[str]] = []

    for a in soup.select("a[href^='/packs/']"):
        # 商品画像のみを対象（altが「料金」や空白は除外）
        imgs = a.find_all("img")
        item_img = None
        item_title = ""
        for img in imgs:
            alt = img.get("alt", "").strip()
            if alt and alt != "料金":
                item_img = img
                item_title = alt
                break
        # 万一見つからない場合はa内のテキスト
        if item_img:
            img_url = item_img["src"]
        else:
            img_url = ""
            item_title = a.get_text(strip=True)

        # 絶対パス化
        if img_url.startswith("/"):
            img_url = urljoin(BASE_URL, img_url)
        detail_url = urljoin(BASE_URL, a.get("href", ""))
        pt_tag = a.select_one("p.chakra-text.css-11ys2a")
        pt = pt_tag.get_text(strip=True) if pt_tag else ""

        rows.append([item_title, img_url, detail_url, pt])
    return rows

def main() -> None:
    sheet = get_sheet()
    rows = fetch_items()
    if not rows:
        print("📭 No data scraped")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} rows")

if __name__ == "__main__":
    main()
