import os
import base64
import time
from datetime import datetime
from typing import List
from urllib.parse import quote

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

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
# 🐦 Twitter DOMベーススクレイピング処理
# ---------------------------

def scrape_tweets_from_dom(limit=10) -> List[List[str]]:
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            locale="ja-JP",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        print(f"🔍 検索URL：{SEARCH_URL}")
        page.goto(SEARCH_URL, timeout=60000)

        try:
            page.wait_for_selector("article", timeout=30000)
        except Exception as e:
            print(f"❌ 'article'要素が見つかりませんでした: {e}")
            page.screenshot(path="debug_article_timeout.png")
            with open("debug_article.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            return []

        page.wait_for_timeout(3000)
        for _ in range(3):
            page.mouse.wheel(0, 1500)
            time.sleep(2)

        tweets = page.locator("article").all()
        print(f"👀 ツイート検出数: {len(tweets)}")

        for tweet in tweets[:limit]:
            try:
                username_el = tweet.locator("a[href^='/' i]").first
                username_href = username_el.get_attribute("href")
                username = username_href.split("/")[1] if username_href else "unknown"

                text_el = tweet.locator("div[data-testid='tweetText']").first
                content = text_el.inner_text().strip() if text_el else ""

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"📝 @{username}: {content}")
                rows.append([timestamp, f"@{username}", content])
            except Exception as e:
                print(f"⚠️ ツイート解析失敗: {e}")

        browser.close()
    return rows

# ---------------------------
# 🚀 メイン処理
# ---------------------------

def main():
    sheet = get_sheet()
    ensure_headers(sheet)
    existing = fetch_existing_texts(sheet)
    tweets = scrape_tweets_from_dom()
    print(f"🎯 検出されたツイート数: {len(tweets)}")

    new_rows = [row for row in tweets if row[2] not in existing]
    print(f"🪛 新規追加対象数: {len(new_rows)}")

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
