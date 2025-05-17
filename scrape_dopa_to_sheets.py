from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import base64
import os
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets 認証 ---
with open("credentials.json", "w") as f:
    f.write(base64.b64decode(os.environ["GSHEET_JSON"]).decode("utf-8"))

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
sheet = spreadsheet.worksheet("dopa")

# --- 既存データ取得（画像URLで重複チェック） ---
existing_data = sheet.get_all_values()[1:]
existing_image_urls = {row[1] for row in existing_data if len(row) > 1}

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    print("🔍 dopa スクレイピング開始...")
    page.goto("https://dopa-game.jp/", timeout=60000, wait_until="networkidle")

    try:
        page.wait_for_selector("div.css-1flrjkp", timeout=60000)
    except Exception as e:
        print("🛑 要素が読み込まれませんでした。", e)
        with open("dopa_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path="dopa_debug.png")
        browser.close()
        exit()

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.css-1flrjkp")
    fallback = False
    if not cards:
        cards = soup.select("a[href^='/pokemon/gacha/'] img")
        fallback = True

    for card in cards:
        if fallback:
            img_tag = card
            a_tag = img_tag.find_parent("a")
        else:
            a_tag = card.select_one("a.css-4g6ai3")
            img_tag = a_tag.select_one("img") if a_tag else None

        if not (a_tag and img_tag):
            continue

        title = img_tag.get("alt", "無題").strip()
        image_url = img_tag.get("src", "")
        detail_url = a_tag.get("href", "") if a_tag else ""

        if image_url.startswith("/"):
            image_url = "https://dopa-game.jp" + image_url
        if detail_url.startswith("/"):
            detail_url = "https://dopa-game.jp" + detail_url

        # ✅ PT数抽出（150だけ）
        if fallback:
            pt_text = ""
        else:
            pt_tag = card.select_one("span.chakra-text.css-19bpybc")
            pt_text = pt_tag.get_text(strip=True) if pt_tag else ""

        # 当たりカード画像をすべて取得
        atari_imgs = []
        if not fallback:
            for atari_div in card.select('div.chakra-aspect-ratio.css-839f3u'):
                img = atari_div.find('img')
                if img and img.get('src'):
                    atari_imgs.append(img['src'])

        # 画像URLをカンマ区切りで保存
        atari_imgs_str = ','.join(atari_imgs)

        if image_url in existing_image_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        print(f"✅ 取得: {title} / {pt_text}PT")
        results.append([title, image_url, detail_url, pt_text, atari_imgs_str])

    browser.close()

# --- スプレッドシートに追記 ---
if results:
    next_row = len(existing_data) + 2
    sheet.update(f"A{next_row}", results)
    print(f"📦 {len(results)} 件追記完了")
else:
    print("📭 新規データなし")
