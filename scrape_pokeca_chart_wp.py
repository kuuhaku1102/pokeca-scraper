import os
import time
import json
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --------------------------------
# WordPress REST API 設定
# --------------------------------
WP_URL = os.getenv("WP_URL", "https://online-gacha-hack.com/wp-json/pokeca/v1/upsert")
WP_LIST_URL = "https://online-gacha-hack.com/wp-json/pokeca/v1/list"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# --------------------------------
# Pokeca-chart の WP-API ベースURL
# --------------------------------
POKECA_API = "https://pokeca-chart.com/wp-json/wp/v2/cards"


# --------------------------------
# 既存URLを取得（重複判定用）
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
# Pokeca-chart REST API で全カードURLを取得
# --------------------------------
def fetch_all_card_urls():

    page = 1
    urls = set()

    print("🔍 pokeca-chart API から全カード一覧を取得…")

    while True:
        api_url = f"{POKECA_API}?per_page=100&page={page}"
        res = requests.get(api_url, timeout=10)

        if res.status_code == 400:  # 上限ページ
            break

        if res.status_code != 200:
            print("⚠️ APIエラー:", res.status_code)
            break

        data = res.json()
        if not data:
            break

        # WP-API の link から詳細ページ URL を取得
        for card in data:
            if "link" in card:
                urls.add(card["link"])

        print(f"📄 API Page {page}: {len(data)} 件 → 累計 {len(urls)} 件")

        page += 1

    print(f"\n🎉 取得カード総数（API）: {len(urls)} 件\n")
    return list(urls)


# --------------------------------
# 詳細ページを取得して価格情報を抽出
# --------------------------------
def fetch_card_detail(url):

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # カード名
        h1 = soup.find("h1")
        card_name = h1.text.strip() if h1 else "noname"

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
            "card_name": card_name,
            "image_url": img_url,
            "detail_url": url,
            "price_json": prices,
        }

    except Exception as e:
        print("⚠️ 詳細ページエラー:", url, e)
        return None


# --------------------------------
# 並列で詳細ページを取得
# --------------------------------
def fetch_details_parallel(urls, existing):
    results = []

    def task(u):
        if u in existing:
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
# WordPress に 20件ずつ送信
# --------------------------------
def send_to_wordpress_batched(items, batch_size=20):

    total = len(items)
    if total == 0:
        print("📭 送信対象なし")
        return

    print(f"🚀 WPへ {total} 件送信開始…")

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        print(f"  → Batch {i//batch_size + 1}: {len(batch)} 件")

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

    # ① API経由で全カード取得（Selenium不要）
    list_urls = fetch_all_card_urls()

    # ② 詳細ページ並列取得
    new_items = fetch_details_parallel(list_urls, existing_urls)

    # ③ WPへ送信
    send_to_wordpress_batched(new_items)

    print(f"\n🏁 完了！（{round(time.time() - start, 2)} 秒）")


if __name__ == "__main__":
    main()
