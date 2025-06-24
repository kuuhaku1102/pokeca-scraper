import os
import base64
import time
import random
from datetime import datetime
from typing import List
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------
# 🔧 設定
# ---------------------------

SEARCH_KEYWORDS = [
    "スパークオリパ 当たり",
    "スパークオリパ 神引き",
    "DOPA当たり"
]

# 拡張インスタンスリスト（信頼性は時期により変動）
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.snopyta.org",
    "https://nitter.fdn.fr",
    "https://nitter.1d4.us",
    "https://nitter.moomoo.me",
    "https://nitter.bus-hit.me",
    "https://nitter.projectsegfau.lt",
    "https://nitter.in.projectsegfau.lt",
    "https://nitter.poast.org"
]

SHEET_NAME = "POST"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


# ---------------------------
# 📄 Google Sheets 連携
# ---------------------------

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


def ensure_headers(sheet):
    headers = sheet.row_values(1)
    expected = ["日時", "ユーザー名", "本文", "画像URL"]
    if headers != expected:
        sheet.insert_row(expected, index=1)


def fetch_existing_texts(sheet) -> set:
    values = sheet.get_all_values()[1:]
    return set(row[2] for row in values if len(row) >= 3)

# ---------------------------
# 💼 Nitter HTML スクレイピング
# ---------------------------

def build_nitter_search_url(base_url: str, keyword: str) -> str:
    q = quote(keyword)
    return f"{base_url}/search?f=tweets&q={q}"


def scrape_nitter(keyword: str, limit: int = 10) -> List[List[str]]:
    for base_url in random.sample(NITTER_INSTANCES, len(NITTER_INSTANCES)):
        url = build_nitter_search_url(base_url, keyword)
        print(f"🔍 検索: {url}")
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if res.status_code == 429:
                print(f"⚠️ {base_url} - 429 Too Many Requests")
                continue
            res.raise_for_status()
        except Exception as e:
            print(f"❌ {base_url} - 接続失敗: {e}")
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("div.timeline-item")

        rows = []
        for item in items[:limit]:
            try:
                user = item.select_one("a.username").text.strip()
                text = item.select_one(".tweet-content").text.strip().replace("\n", " ")
                time_tag = item.select_one("span.tweet-date > a")
                date_str = time_tag["title"] if time_tag and "title" in time_tag.attrs else datetime.now().isoformat()
                date_obj = datetime.fromisoformat(date_str)
                img_el = item.select_one(".attachment.image > a")
                img_url = base_url + img_el["href"] if img_el else ""
                rows.append([date_obj.strftime("%Y-%m-%d %H:%M:%S"), user, text, img_url])
            except Exception as e:
                print(f"⚠️ 解析失敗: {e}")
        if rows:
            return rows
        else:
            print(f"⚠️ {base_url} にデータが見つかりませんでした")
        time.sleep(5)
    return []

# ---------------------------
# ▶ メイン
# ---------------------------

def main():
    sheet = get_sheet()
    ensure_headers(sheet)
    existing = fetch_existing_texts(sheet)

    all_rows = []
    for keyword in SEARCH_KEYWORDS:
        rows = scrape_nitter(keyword, limit=10)
        for row in rows:
            if row[2] not in existing:
                all_rows.append(row)
        print(f"⌛ 検索後のウェイト...")
        time.sleep(600)  # 各検索語で10分間隔

    print(f"🌟 新規追加対象: {len(all_rows)}")
    if not all_rows:
        print("📭 No new data to append")
        return

    try:
        sheet.append_rows(all_rows, value_input_option="USER_ENTERED")
        print(f"📅 {len(all_rows)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッド書き込み失敗: {e}")


if __name__ == "__main__":
    main()
