import os
import time
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --------------------------------
# WordPress REST API 設定
# --------------------------------
WP_URL = os.getenv("WP_URL", "https://online-gacha-hack.com/wp-json/pokeca/v1/upsert")
WP_LIST_URL = "https://online-gacha-hack.com/wp-json/pokeca/v1/list"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# --------------------------------
# Selenium（ヘッドレス Chrome）
# --------------------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1280,2000")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# --------------------------------
# 既存 URL一覧取得（重複排除用）
# --------------------------------
def fetch_existing_urls() -> set:
    try:
        res = requests.get(WP_LIST_URL, auth=(WP_USER, WP_APP_PASS), timeout=20)
        if res.status_code != 200:
            print("⚠️ 既存URL取得失敗:", res.status_code)
            return set()
        urls = set(res.json())
        print(f"🔎 既存URL数: {len(urls)} 件")
        return urls
    except Exception as e:
        print("🛑 URL取得中にエラー:", e)
        return set()


# --------------------------------
# pokeca-chart の全20ページからカード取得
# --------------------------------
def get_card_urls(max_pages=20):

    print("🔍 pokeca-chart.com 全20ページをクロール中…")

    urls = set()

    for page_num in range(1, max_pages + 1):

        list_url = f"https://pokeca-chart.com/all-card?mode={page_num}"
        print(f"\n📄 ページ取得中: {list_url}")

        driver.get(list_url)
        time.sleep(2)

        # SPA対策：1回スクロール
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # ★ 正しいカード要素
        cards = soup.select("div.cp_card.hover_big")

        print(f"  → ページ {page_num}: {len(cards)} 件")

        for card in cards:
            a_tag = card.find("a", href=True)
            if not a_tag:
                continue

            href = a_tag["href"].strip()

            # pokeca-chart 内のURLのみ許可
            if href.startswith("https://pokeca-chart.com/"):
                urls.add(href)

    print(f"\n🎉 合計 {len(urls)} 件のカードURLを取得\n")
    return list(urls)


# --------------------------------
# カード詳細ページのスクレイプ
# --------------------------------
def fetch_card_detail(url):

    driver.get(url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # ① カード名
    name_tag = soup.find("h1")
    card_name = name_tag.text.strip() if name_tag else "noname"

    # ② 画像URL
    img_url = ""
    img = soup.find("img")
    if img and img.get("src"):
        img_url = img["src"]
        if not img_url.startswith("http"):
            img_url = "https://pokeca-chart.com" + img_url

    # ③ 価格JSON（テーブル形式）
    prices = {"美品": "", "キズあり": "", "PSA10": ""}

    table = soup.find("tbody", id="item-price-table")

    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            cols = rows[1].find_all("td")
            if len(cols) >= 4:
                prices["美品"] = cols[1].get_text(strip=True)
                prices["キズあり"] = cols[2].get_text(strip=True)
                prices["PSA10"] = cols[3].get_text(strip=True)

    return {
        "card_name": card_name,
        "image_url": img_url,
        "detail_url": url,
        "price_json": prices,
    }


# --------------------------------
# WordPressへ投稿
# --------------------------------
def send_to_wordpress(items):

    if not items:
        print("📭 新規データなし → スキップ")
        return

    print(f"🚀 WordPressへ {len(items)} 件送信中…")

    res = requests.post(
        WP_URL,
        json=items,
        auth=(WP_USER, WP_APP_PASS),
        timeout=40
    )

    print("Status:", res.status_code)

    try:
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
    except:
        print(res.text)


# --------------------------------
# メイン処理
# --------------------------------
def main():

    start = time.time()

    existing = fetch_existing_urls()

    card_urls = get_card_urls(max_pages=20)

    new_items = []

    for url in card_urls:
        if url in existing:
            print("⏭ 重複スキップ:", url)
            continue

        detail = fetch_card_detail(url)
        new_items.append(detail)

    send_to_wordpress(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）")


if __name__ == "__main__":
    main()
