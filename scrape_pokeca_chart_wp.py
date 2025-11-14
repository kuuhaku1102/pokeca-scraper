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
# 既存 URL一覧取得（重複除外用）
# --------------------------------
def fetch_existing_urls() -> set:
    try:
        res = requests.get(WP_LIST_URL, auth=(WP_USER, WP_APP_PASS), timeout=20)
        if res.status_code != 200:
            print("⚠️ 既存URL取得に失敗:", res.status_code)
            return set()
        urls = set(res.json())
        print(f"🔎 既存URL数: {len(urls)} 件")
        return urls
    except Exception as e:
        print("🛑 URL取得エラー:", e)
        return set()


# --------------------------------
# 全20ページをスクロールしながらクロール
# --------------------------------
def get_card_urls(max_pages=20):
    print("🔍 pokeca-chart.com のカード一覧を全ページクロール中...")

    urls = set()

    for page_num in range(1, max_pages + 1):
        list_url = f"https://pokeca-chart.com/all-card?mode={page_num}"
        print(f"\n📄 ページ取得中: {list_url}")

        try:
            driver.get(list_url)
            time.sleep(1)

            # 🔥 ページ読み込み安定化（スクロール）
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            cards = soup.find_all("div", class_="cp_card04")
            print(f"  → ページ {page_num}: {len(cards)} 件")

            for card in cards:
                a = card.find("a", href=True)
                if not a:
                    continue
                href = a["href"].strip()
                if href.startswith("https://pokeca-chart.com/s"):
                    urls.add(href)

        except Exception as e:
            print(f"🛑 ページ {page_num} の取得中にエラー:", e)
            # エラーがあっても停止しない
            continue

    print(f"\n🎉 合計 {len(urls)} 件のカードURLを取得\n")
    return list(urls)


# --------------------------------
# カード詳細ページから情報収集
# --------------------------------
def fetch_card_detail(url: str):
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # カード名
    name_tag = soup.find("h1")
    card_name = name_tag.text.strip() if name_tag else "noname"

    # 画像
    img = soup.find("img")
    img_url = ""
    if img and img.get("src"):
        img_url = img["src"]
        if not img_url.startswith("http"):
            img_url = "https://pokeca-chart.com" + img_url

    # 価格表
    prices = {"美品": "", "キズあり": "", "PSA10": ""}

    table = soup.find("tbody", id="item-price-table")
    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            cols = rows[1].find_all("td")
            if len(cols) >= 4:
                prices["美品"] = cols[1].text.strip()
                prices["キズあり"] = cols[2].text.strip()
                prices["PSA10"] = cols[3].text.strip()

    return {
        "card_name": card_name,
        "image_url": img_url,
        "detail_url": url,
        "price_json": prices,
    }


# --------------------------------
# WP REST API へ送信
# --------------------------------
def send_to_wordpress(items):
    if not items:
        print("📭 新規データなし → 投稿スキップ")
        return

    print(f"🚀 WordPressへ {len(items)} 件送信中...")

    try:
        res = requests.post(
            WP_URL,
            json=items,
            auth=(WP_USER, WP_APP_PASS),
            timeout=40
        )

        print("Status:", res.status_code)

        try:
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(res.text)

    except Exception as e:
        print("🛑 送信エラー:", e)


# --------------------------------
# メイン処理
# --------------------------------
def main():
    start = time.time()

    existing_urls = fetch_existing_urls()
    all_urls = get_card_urls(max_pages=20)

    new_items = []

    for url in all_urls:
        if url in existing_urls:
            print(f"⏭ 重複スキップ: {url}")
            continue

        detail = fetch_card_detail(url)
        new_items.append(detail)

    send_to_wordpress(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）\n")


if __name__ == "__main__":
    main()
