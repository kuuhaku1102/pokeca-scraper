import os
import time
import json
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
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
# Selenium 設定
# --------------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1280,2000")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# --------------------------------
# 既存URL取得
# --------------------------------
def fetch_existing_urls():
    try:
        res = requests.get(WP_LIST_URL, auth=(WP_USER, WP_APP_PASS), timeout=20)
        urls = set(res.json())
        print(f"🔎 既存 {len(urls)} 件")
        return urls
    except Exception as e:
        print("🛑 URL取得エラー:", e)
        return set()


# --------------------------------
# /all-card を無限スクロールして全カードURLを抽出
# --------------------------------
def fetch_all_card_urls(scroll_count=150):

    print(f"🔍 /all-card を {scroll_count} 回スクロールして全カード取得…")

    driver.get("https://pokeca-chart.com/all-card")
    time.sleep(2)

    last_height = 0

    for i in range(scroll_count):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.2)  # ページ読み込み待機
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(f"⚠️ スクロール {i}で高さ変化なし → それ以上カードは増えない可能性")
            break
        last_height = new_height
        print(f"  → スクロール {i+1}/{scroll_count}")

    soup = BeautifulSoup(driver.page_source, "html.parser")

    urls = set()

    # カードURLの共通パターン
    pattern = re.compile(r"^https://pokeca-chart\.com/[a-z0-9\-]+$", re.IGNORECASE)

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # 相対パス → 絶対URL化
        if href.startswith("/"):
            href = "https://pokeca-chart.com" + href

        if pattern.match(href):
            urls.add(href)

    print(f"\n🎉 最終取得カードURL総数: {len(urls)} 件\n")
    return list(urls)


# --------------------------------
# 詳細ページスクレイピング（requests高速版）
# --------------------------------
def fetch_card_detail(url):

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # ① カード名
        h1 = soup.find("h1")
        card_name = h1.text.strip() if h1 else "noname"

        # ② 画像
        img_url = ""
        img = soup.find("img")
        if img and img.get("src"):
            img_url = img["src"]
            if not img_url.startswith("http"):
                img_url = "https://pokeca-chart.com" + img_url

        # ③ 価格 JSON
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

    except Exception as e:
        print("⚠️ 詳細取得失敗:", url, e)
        return None


# --------------------------------
# 並列で詳細ページを取得
# --------------------------------
def fetch_details_parallel(urls, existing):

    print("🔄 詳細ページを並列取得中…")
    results = []

    def task(u):
        if u in existing:
            print(" ⏭ 重複:", u)
            return None
        return fetch_card_detail(u)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(task, u) for u in urls]
        for f in as_completed(futures):
            data = f.result()
            if data:
                results.append(data)

    print(f"📦 新規カード総数: {len(results)} 件")
    return results


# --------------------------------
# WordPressへ 20件ずつ送信
# --------------------------------
def send_to_wp_batched(items, batch_size=20):

    if not items:
        print("📭 送信対象なし")
        return

    total = len(items)
    print(f"🚀 WPへ {total} 件送信開始…")

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        print(f" → Batch {i//batch_size+1}: {len(batch)} 件")

        try:
            res = requests.post(
                WP_URL,
                json=batch,
                auth=(WP_USER, WP_APP_PASS),
                timeout=60
            )
            print("Status:", res.status_code)
            print(res.text)
        except Exception as e:
            print("🛑 バッチ送信エラー:", e)


# --------------------------------
# メイン処理
# --------------------------------
def main():

    start = time.time()

    existing_urls = fetch_existing_urls()

    # Step1: /all-card を150回スクロールして全URL取得
    list_urls = fetch_all_card_urls(scroll_count=150)

    # Step2: 詳細ページを並列取得
    new_items = fetch_details_parallel(list_urls, existing_urls)

    # Step3: WP にバッチ送信
    send_to_wp_batched(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）")


if __name__ == "__main__":
    main()
