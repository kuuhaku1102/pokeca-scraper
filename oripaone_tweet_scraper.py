import os
import base64
import time
from datetime import datetime
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://twitter.com/search?q=オリパワン%20当たり&f=live"
SHEET_NAME = "POST"  # ←必要に応じて"その他"などと変更してください
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


def ensure_headers(sheet):
    headers = sheet.row_values(1)
    expected = ["日時", "ユーザー名", "本文"]
    if headers != expected:
        sheet.insert_row(expected, index=1)


def fetch_existing_texts(sheet) -> set:
    values = sheet.get_all_values()[1:]
    return set(row[2] for row in values if len(row) >= 3)


def scrape_tweets(limit=5) -> List[List[str]]:
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile Safari/604.1")
        page = context.new_page()
        page.goto(SEARCH_URL, timeout=60000)
        time.sleep(5)

        tweets = page.locator("article").all()
        for tweet in tweets[:limit]:
            try:
                text = tweet.inner_text()
                lines = text.split('\n')
                if len(lines) < 2:
                    continue
                username = lines[0].lstrip("@").strip()
                content = " ".join(lines[1:]).strip()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows.append([timestamp, username, content])
            except Exception as e:
                print(f"⚠️ ツイート解析失敗: {e}")
        browser.close()
    return rows


def main():
    sheet = get_sheet()
    ensure_headers(sheet)
    existing = fetch_existing_texts(sheet)
    tweets = scrape_tweets()
    new_rows = [row for row in tweets if row[2] not in existing]

    if not new_rows:
        print("📭 新規データなし")
        return

    try:
        sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(new_rows)} 件追記完了")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")


if __name__ == "__main__":
    main()
