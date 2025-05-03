import os
import base64
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# 認証ファイルの生成
CREDENTIALS_FILE = "credentials.json"
with open(CREDENTIALS_FILE, "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode())

# Google Sheets認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
gc = gspread.authorize(credentials)

# スプレッドシートURLで開く
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit").sheet1

def scrape_oripaone():
    url = "https://oripaone.jp/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    card_divs = soup.select("div.grid > div.relative.bg-white.shadow")
    results = []
    for card in card_divs:
        a_tag = card.find("a", href=True)
        img_tag = card.find("img", src=True)
        if a_tag and img_tag:
            full_url = "https://oripaone.jp" + a_tag["href"]
            img_url = img_tag["src"]
            title = img_tag.get("alt", "").strip() or "No Title"
            results.append([title, img_url, full_url])
    return results

def save_to_sheet(data):
    # ヘッダーがなければ追加
    if sheet.cell(1, 1).value != "タイトル":
        sheet.clear()
        sheet.insert_row(["タイトル", "画像URL", "URL"], 1)
    existing_titles = sheet.col_values(1)[1:]  # 2行目以降

    next_row = len(existing_titles) + 2
    for title, img_url, url in data:
        if title in existing_titles:
            continue
        sheet.update(f"A{next_row}:C{next_row}", [[title, img_url, url]])
        next_row += 1

def main():
    print("🔍 oripaone スクレイピング開始...")
    data = scrape_oripaone()
    print(f"✅ 取得件数: {len(data)} 件")
    save_to_sheet(data)

if __name__ == "__main__":
    main()
