import os
import base64
import json
import time
from datetime import datetime
from typing import List
from urllib.parse import quote

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright, Response

# ---------------------------
# 🔧 設定
# ---------------------------

SEARCH_KEYWORDS = [
    "スパークオリパ 当たり",
    "スパークオリパ 神引き",
    "DOPA当選報告"
]

SHEET_NAME = "POST"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


def build_search_url(keywords: List[str]) -> str:
    query = " OR ".join(keywords)
    encoded = quote(query)
    return f"https://twitter.com/search?q={encoded}&f=live"

SEARCH_URL = build_search_url(SEARCH_KEYWORDS)

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
    expected = ["日時", "ユーザー名", "本文"]
    if headers != expected:
        sheet.insert_row(expected, index=1)


def fetch_existing_texts(sheet) -> set:
    values = sheet.get_all_values()[1:]
    return set(row[2] for row in values if len(row) >= 3)

# ---------------------------
# 🐦 Twitter XHR 取得処理
# ---------------------------

def scrape_tweets_from_xhr(limit=10) -> List[List[str]]:
    rows = []
    tweets_json: List[dict] = []

    def capture_response(response: Response):
        try:
            if "Adaptive" in response.url and "SearchTimeline" in response.url:
                json_data = response.json()
                tweets_json.append(json_data)
        except Exception as e:
            print(f"⚠️ JSON取得失敗: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            locale="ja-JP"
        )
        page = context.new_page()
        page.on("response", capture_response)

        print(f"🔍 検索URL：{SEARCH_URL}")
        page.goto(SEARCH_URL, timeout=60000)
        page.wait_for_timeout(8000)
        for _ in range(3):
            page.mouse.wheel(0, 1500)
            time.sleep(2)

        page.screenshot(path="xhr_debug.png")

        browser.close()

    tweets_data = {}
    users_data = {}

    for data in tweets_json:
        if "globalObjects" in data:
            tweets_data.update(data["globalObjects"].get("tweets", {}))
            users_data.update(data["globalObjects"].get("users", {}))

    print(f"📦 取得ツイート数: {len(tweets_data)}")

    count = 0
    for tweet_id, tweet in tweets_data.items():
        if count >= limit:
            break
        text = tweet.get("full_text", "").replace("\n", " ").strip()
        user_id = tweet.get("user_id_str")
        username = users_data.get(user_id, {}).get("screen_name", "unknown")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"📝 @{username}: {text}")
        rows.append([timestamp, f"@{username}", text])
        count += 1

    with open("xhr_raw.json", "w", encoding="utf-8") as f:
        json.dump(tweets_json, f, ensure_ascii=False, indent=2)

    return rows

# ---------------------------
# 🚀 メイン処理
# ---------------------------

def main():
    sheet = get_sheet()
    ensure_headers(sheet)
    existing = fetch_existing_texts(sheet)
    tweets = scrape_tweets_from_xhr()
    print(f"🎯 検出されたツイート数: {len(tweets)}")

    new_rows = [row for row in tweets if row[2] not in existing]
    print(f"🧹 新規追加対象数: {len(new_rows)}")

    if not new_rows:
        print("📭 No new data to append")
        return

    try:
        sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(new_rows)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")


if __name__ == "__main__":
    main()
