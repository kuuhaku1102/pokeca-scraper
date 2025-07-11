import os
import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import gspread
from google.oauth2.service_account import Credentials

BASE_URL = "https://dopa-game.jp/"
SHEET_NAME = "news"
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

def fetch_existing_image_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 1:
            urls.add(row[0].strip())
    return urls

def scrape_banners(existing_urls: set):
    print("🌐 Downloading HTML...")
    try:
        res = requests.get(BASE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        res.raise_for_status()
    except Exception as e:
        print(f"🛑 ページ取得失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")

    print("🔍 Searching swiper images...")
    rows = []
    skipped = 0
    for img in soup.select(".swiper-slide img"):
        src = img.get("src")
        if not src:
            continue
        full_url = urljoin(BASE_URL, src.strip())
        if full_url in existing_urls:
            skipped += 1
            continue
        rows.append([full_url, BASE_URL])  # B列には BASE_URL を固定出力
        existing_urls.add(full_url)

    print(f"✅ {len(rows)} new banner(s) found, {skipped} skipped (already existed)")
    return rows

def main():
    print("🚀 Start")
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 No new banners")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 Appended {len(rows)} new rows")

if __name__ == "__main__":
    main()
