import os
import time
import json
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
# Selenium（一覧ページだけ使用）
# --------------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1280,2000")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# --------------------------------
# 既存 URL一覧取得（重複除外用）
# --------------------------------
def fetch_existing_urls():
    try:
        res = requests.get(WP_LIST_URL, auth=(WP_USER, WP_APP_PASS), timeout=20)
        if res.status_code != 200:
            print("⚠️ 既存URL取得失敗:", res.status_code)
            return set()
        urls = set(res.json())
        print(f"🔎 既存 {len(urls)} 件")
        return urls
    except Exception as e:
        print("🛑 URL取得エラー:", e)
        return set()


# --------------------------------
# 一覧ページ 1ページ分のURLを収集（複数セレクタ対応版）
# --------------------------------
def scrape_list_page(page_num):
    url = f"https://pokeca-chart.com/all-card?mode={page_num}"

    try:
        driver.get(url)
        time.sleep(1.2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        urls = set()

        # ① ランキング系カード
        for a in soup.select("div.cp_card.hover_big a[href]"):
            href = a["href"].strip()
            if href.startswith("/"):
                href = "https://pokeca-chart.com" + href
            if href.startswith("https://pokeca-chart.com/"):
                urls.add(href)

        # ② cp_card04（旧式の一覧構造）
        for a in soup.select("div.cp_card04 a[href]"):
            href = a["href"].strip()
            if href.startswith("/"):
                href = "https://pokeca-chart.com" + href
            if href.startswith("https://pokeca-chart.com/"):
                urls.add(href)

        # ③ JSONレンダリング系（最新のデザイン）
        for a in soup.select("a.card_link[href]"):
            href = a["href"].strip()
            if href.startswith("/"):
                href = "https://pokeca-chart.com" + href
            if href.startswith("https://pokeca-chart.com/"):
                urls.add(href)

        print(f"📄 Page {page_num}: {len(urls)} 件")
        return urls

    except Exception as e:
        print(f"🛑 Page {page_num} エラー:", e)
        return set()


# --------------------------------
# 全20ページを並列クロール
# --------------------------------
def get_all_card_urls(max_pages=20):
    print("🔍 pokeca-chart.com 全20ページクロール…")

    urls = set()

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(scrape_list_page, i) for i in range(1, max_pages + 1)]
        for f in as_completed(futures):
            for u in f.result():
                urls.add(u)

    print(f"\n🎉 最終取得カードURL総数: {len(urls)} 件\n")
    return list(urls)


# --------------------------------
# 詳細ページ取得（高速 requests）
# --------------------------------
def fetch_card_detail(url):

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

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

        # ③ 価格
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

    except Exception as e:
        print("⚠️ Detailエラー:", url, e)
        return None


# --------------------------------
# 詳細ページを並列取得
# --------------------------------
def fetch_details_parallel(urls, existing):

    results = []

    def task(u):
        if u in existing:
            print("⏭ 重複:", u)
            return None
        return fetch_card_detail(u)

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(task, u) for u in urls]
        for f in as_completed(futures):
            data = f.result()
            if data:
                results.append(data)

    print(f"\n📦 新規カード総数: {len(results)} 件\n")
    return results


# --------------------------------
# 100件単位で WordPress に送信
# --------------------------------
def send_to_wordpress_batched(items, batch_size=100):

    total = len(items)
    if total == 0:
        print("📭 送信対象なし")
        return

    print(f"🚀 WPへ {total} 件送信開始…")

    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        print(f" → Batch {i // batch_size + 1}: {len(batch)} 件")

        try:
            res = requests.post(
                WP_URL,
                json=batch,
                auth=(WP_USER, WP_APP_PASS),
                timeout=40
            )
            print("Status:", res.status_code)
            try:
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
            except:
                print(res.text)

        except Exception as e:
            print("🛑 バッチ送信エラー:", e)


# --------------------------------
# メイン処理
# --------------------------------
def main():

    start = time.time()

    existing_urls = fetch_existing_urls()

    # Step1: 全20ページのURLを並列取得
    list_urls = get_all_card_urls(max_pages=20)

    # Step2: 詳細ページを並列取得
    new_items = fetch_details_parallel(list_urls, existing_urls)

    # Step3: WordPress へバッチ送信
    send_to_wordpress_batched(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）")


if __name__ == "__main__":
    main()
