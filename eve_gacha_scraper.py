import os
import base64
import re
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

BASE_URL = "https://eve-gacha.com/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def save_credentials() -> str:
    """Decode credentials from env and write to file."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
    """Return worksheet object for the target sheet."""
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
    """Fetch existing detail URLs (絶対パスで比較)"""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:] if len(records) > 1 else []:
        if len(row) >= 3:
            url = row[2].strip()
            url_set.add(url)
    return url_set

def extract_pt(text: str) -> str:
    """ガチャ価格PT部分だけ抽出"""
    m = re.search(r"(\d{3,6})", text.replace(",", ""))
    return m.group(1) if m else ""

def fetch_items(existing_urls: set) -> List[List[str]]:
    """eve-gacha.comトップからガチャ情報抽出"""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: List[List[str]] = []

    # --- デバッグ: 取得できているか確認 ---
    links = soup.select("a[href*='/gacha/']")
    print(f"取得したaタグ数: {len(links)}")
    if len(links) == 0:
        print("⚠️ 取得aタグゼロ：サイト構造変化やCloudflare対策の可能性あり")
    # --- ここまでデバッグ ---

    for a in links:
        detail_url = a.get("href", "").strip()
        if not detail_url:
            continue
        # 絶対パス化
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        detail_url = detail_url.strip()
        if detail_url in existing_urls:
            continue

        # 1つ上のdiv.card風親要素から情報を取得
        container = a.find_parent("div") or a
        img = a.find("img")
        image_url = ""
        title = "noname"
        if img:
            image_url = img.get("data-src") or img.get("src", "")
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)
            image_url = image_url.strip()
            alt = img.get("alt") or img.get("title")
            if alt:
                title = alt.strip() or title

        # タイトルが未取得ならテキスト拾う
        if title == "noname":
            text = " ".join(t.strip() for t in container.stripped_strings if t.strip())
            if text:
                title = text.split()[0]

        pt_text = a.get_text(" ", strip=True)
        pt = extract_pt(pt_text)
        # 念のためタイトル/画像/PTいずれか空欄の場合もスキップしない（お好みで調整可）

        rows.append([title, image_url, detail_url, pt])
        existing_urls.add(detail_url)  # 追加済みに

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
