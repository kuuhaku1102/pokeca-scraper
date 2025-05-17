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

def fetch_existing_urls(sheet) -> set:
    """既存のdetail_urlをセットで取得（4列目と仮定）"""
    records = sheet.get_all_values()
    # 1行目がヘッダーの場合は records[1:] から始める
    url_set = set()
    for row in records[1:] if len(records) > 1 else []:
        if len(row) >= 3:
            url_set.add(row[2])
    return url_set

def fetch_items(existing_urls: set) -> List[List[str]]:
    """Scrape gacha info from sparkoripa.jp, skipping already recorded URLs."""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: List[List[str]] = []

    for a in soup.select("a[href^='/packs/']"):
        detail_url = urljoin(BASE_URL, a.get("href", ""))
        # 重複があればスキップ
        if detail_url in existing_urls:
            continue
        img_url = detail_url
        text_candidates = [t.strip() for t in a.stripped_strings if t.strip()]
        title = max(text_candidates, key=len) if text_candidates else "noname"
        pt_tag = a.select_one("p.chakra-text.css-11ys2a")
        pt = pt_tag.get_text(strip=True) if pt_tag else ""

        rows.append([title, img_url, detail_url, pt])
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
