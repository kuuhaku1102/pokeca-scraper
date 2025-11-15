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
# Selenium 設定（一覧ページのみで使用）
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
        if res.status_code != 200:
            print("⚠️ 既存URL取得失敗:", res.status_code)
            return set()
        urls = set(res.json())
        print(f"🔎 既存 {len(urls)} 件")
        return urls
    except Exception as e:
        print("🛑 URL取得中エラー:", e)
        return set()


# --------------------------------
# 1ページ分のカードURL取得
# --------------------------------
def scrape_list_page(page_num):
    url = f"https://pokeca-chart.com/all-card?mode={page_num}"

    try:
        driver.get(url)
        time.sleep(1.2)

        # 安定スクロール
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("div.cp_card.hover_big")

        urls = []
        for card in cards:
            a = card.find("a", href=True)
            if a:
                href = a["href"].strip()
                if href.startswith("https://pokeca-chart.com/"):
                    urls.append(href)

        print(f"📄 Page {page_num}: {len(urls)} 件")
        return urls

    except Exception as e:
        print(f"🛑 Page {page_num} エラー: {e}")
        return []


# --------------------------------
# 全20ページを並列取得
# --------------------------------
def get_all_card_urls(max_pages=20):
    urls = set()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(scrape_list_page, i) for i in range(1, max_pages+1)]
        for f in as_completed(futures):
            for u in f.result():
                urls.add(u)

    print(f"\n🎉 一覧URL総数: {len(urls)} 件\n")
    return list(urls)


# --------------------------------
# カード詳細を requests で取得（超高速）
# --------------------------------
def fetch_card_detail(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # カード名
        name_tag = soup.find("h1")
        name = name_tag.text.strip() if name_tag else "noname"

        # 画像
        img_url = ""
        img = soup.find("img")
        if img and img.get("src"):
            img_url = img["src"]
            if not img_url.startswith("http"):
                img_url = "https://pokeca-chart.com" + img_url

        # 価格テーブル
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
            "card_name": name,
            "image_url": img_url,
            "detail_url": url,
            "price_json": prices,
        }

    except Exception as e:
        print("⚠️ Detail エラー:", url, e)
        return None


# --------------------------------
# カード詳細を並列取得
# --------------------------------
def fetch_details_parallel(urls, existing):
    results = []

    def task(u):
        if u in existing:
            print("⏭ 重複スキップ:", u)
            return None
        return fetch_card_detail(u)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(task, u) for u in urls]
        for f in as_completed(futures):
            d = f.result()
            if d:
                results.append(d)

    print(f"\n📦 新規カード総数: {len(results)} 件\n")
    return results


# --------------------------------
# WordPress に 100件単位で送信
# --------------------------------
def send_to_wordpress_batched(items, batch_size=100):

    total = len(items)
    if total == 0:
        print("📭 送信対象なし")
        return

    print(f"🚀 WP へ {total} 件送信開始…")

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        print(f" → Batch {i//batch_size+1}: {len(batch)} 件")

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

    # Step1: 一覧URLを並列で20ページ分取得
    list_urls = get_all_card_urls(max_pages=20)

    # Step2: 詳細ページを並列で取得（requests）
    new_items = fetch_details_parallel(list_urls, existing_urls)

    # Step3: WPへバッチ送信
    send_to_wordpress_batched(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）")


if __name__ == "__main__":
    main()
