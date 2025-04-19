import base64, os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials  # ✅ これが必須
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pymysql
import json


# スプレッドシートへ出力
# Google Sheets認証設定
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# ✅ 必ずこの行を追加！
sheet = client.open(SPREADSHEET_NAME).sheet1

# スプレッドシートへ出力
sheet.clear()

# ✅ MySQLに保存開始
import pymysql
import json

# DB接続
conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    charset='utf8mb4'
)
cursor = conn.cursor()

for card in results:
    sql = """
    INSERT INTO wp_pokeca_prices (
        card_title, image_url, card_url,
        price_b, price_k, price_p
    ) VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (
        card["カード名"],
        card["画像"],
        card["URL"],
        json.dumps({
            "データ数": card["美品_データ数"],
            "直近価格": card["美品_直近価格"],
            "最高価格": card["美品_最高価格"],
            "平均価格": card["美品_平均価格"],
            "最低価格": card["美品_最低価格"],
            "騰落率(7日)": card["美品_騰落率(7日)"],
            "騰落率(30日)": card["美品_騰落率(30日)"]
        }, ensure_ascii=False),
        json.dumps({
            "データ数": card["キズあり_データ数"],
            "直近価格": card["キズあり_直近価格"],
            "最高価格": card["キズあり_最高価格"],
            "平均価格": card["キズあり_平均価格"],
            "最低価格": card["キズあり_最低価格"],
            "騰落率(7日)": card["キズあり_騰落率(7日)"],
            "騰落率(30日)": card["キズあり_騰落率(30日)"]
        }, ensure_ascii=False),
        json.dumps({
            "データ数": card["PSA10_データ数"],
            "直近価格": card["PSA10_直近価格"],
            "最高価格": card["PSA10_最高価格"],
            "平均価格": card["PSA10_平均価格"],
            "最低価格": card["PSA10_最低価格"],
            "騰落率(7日)": card["PSA10_騰落率(7日)"],
            "騰落率(30日)": card["PSA10_騰落率(30日)"]
        }, ensure_ascii=False),
    ))

conn.commit()
cursor.close()
conn.close()

print("✅ MySQLにも保存完了しました！")
