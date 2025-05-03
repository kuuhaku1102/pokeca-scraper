import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# 環境変数から読み込み
SPREADSHEET_NAME = os.getenv("GSHEET_NAME", "OripaGachaList")
WORKSHEET_NAME = os.getenv("GSHEET_SHEET", "dash")
CREDENTIALS_FILE = os.getenv("GSHEET_JSON", "credentials.json")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

def scrape_oripa_dash():
    url = "https://oripa-dash.com/user/packList"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    pack_list = []
    for item in soup.select(".cardListItem"):
        title = item.select_one(".title").text.strip()
        date = item.select_one(".date").text.strip()
        href = item.select_one("a")["href"]
        pack_id = href.split("/")[-1]
        link = f"https://oripa-dash.com/user/itemDetail?id={pack_id}"
        pack_list.append([title, date, link])

    return pack_list

def save_to_sheet(data):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open(SPREADSHEET_NAME)
    ws = sh.worksheet(WORKSHEET_NAME)
    ws.clear()
    ws.append_row(["タイトル", "日付", "URL"])
    for row in data:
        ws.append_row(row)

def post_to_wordpress(title, date, link):
    endpoint = f"{WP_URL}/wp-json/wp/v2/posts"
    auth = (WP_USER, WP_APP_PASS)
    content = f"<p>更新日: {date}</p><p><a href='{link}'>{link}</a></p>"
    post_data = {
        "title": title,
        "content": content,
        "status": "publish"
    }
    res = requests.post(endpoint, json=post_data, auth=auth)
    res.raise_for_status()
    print(f"投稿成功: {res.json().get('link')}")

def main():
    data = scrape_oripa_dash()
    save_to_sheet(data)
    # 最初の1件だけ投稿（本番運用ではループ可能）
    if data:
        post_to_wordpress(data[0][0], data[0][1], data[0][2])

if __name__ == "__main__":
    main()
