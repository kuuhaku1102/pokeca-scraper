import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

def scrape_oripa_dash():
    """オリパダッシュのガチャタイトルと画像URLを取得"""
    url = "https://oripa-dash.com/user/packList"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    items = soup.select(".packList__item")

    for item in items:
        # タイトルは data-pack-name にある
        title = item.get("data-pack-name", "No Title").strip()

        # 画像URLは img.packList__item-thumbnail の src 属性
        img_tag = item.select_one("img.packList__item-thumbnail")
        img_url = img_tag.get("src") if img_tag else ""

        if img_url.startswith("/"):
            img_url = "https://oripa-dash.com" + img_url

        results.append([title, img_url])

    return results

def save_to_sheet(data):
    """Google Sheets 'OripaGachaList' の 'dash' シートに書き込み"""
    gsheet_json = os.getenv("GSHEET_JSON")
    if not gsheet_json:
        raise EnvironmentError("GSHEET_JSON 環境変数が未設定です。")

    creds_dict = json.loads(gsheet_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    client = gspread.authorize(credentials)
    sheet = client.open("OripaGachaList").worksheet("dash")

    # 初期化 & ヘッダー挿入
    sheet.clear()
    sheet.append_row(["タイトル", "画像URL"])

    for row in data:
        sheet.append_row(row)

if __name__ == "__main__":
    try:
        print("🟡 スクレイピング開始...")
        data = scrape_oripa_dash()
        print(f"🟢 {len(data)} 件のデータを取得しました。")

        print("📤 Google Sheets に保存中...")
        save_to_sheet(data)

        print("✅ 完了しました！")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        exit(1)
