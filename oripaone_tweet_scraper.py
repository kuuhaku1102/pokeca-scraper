import os
import base64
from typing import List

import certifi

# Ensure snscrape uses an up-to-date certificate bundle
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import gspread
from google.oauth2.service_account import Credentials
import snscrape.modules.twitter as sntwitter

SHEET_NAME = "その他"
QUERY = "オリパワン 当たり報告"
MAX_TWEETS = 50


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
    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not spreadsheet_url:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(spreadsheet_url)
    return spreadsheet.worksheet(SHEET_NAME)


def ensure_headers(sheet, headers: List[str]):
    current = sheet.row_values(1)
    if current[: len(headers)] != headers:
        sheet.update(values=[headers], range_name="A1")


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()[1:]
    urls = set()
    for row in records:
        if len(row) >= 4:
            urls.add(row[3].strip())
    return urls


def search_tweets(query: str, limit: int):
    tweets = []
    try:
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i >= limit:
                break
            tweets.append(tweet)
    except Exception as exc:  # noqa: BLE001
        print(f"🛑 Failed to fetch tweets: {exc}")
    return tweets


def main() -> None:
    sheet = get_sheet()
    headers = ["Date", "User", "Text", "URL"]
    ensure_headers(sheet, headers)
    existing_urls = fetch_existing_urls(sheet)
    tweets = search_tweets(QUERY, MAX_TWEETS)
    rows = []
    for tw in tweets:
        url = f"https://twitter.com/{tw.user.username}/status/{tw.id}"
        if url in existing_urls:
            continue
        text = tw.content.replace("\n", " ")
        date = tw.date.strftime("%Y-%m-%d %H:%M:%S")
        rows.append([date, tw.user.username, text, url])
        existing_urls.add(url)
    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
