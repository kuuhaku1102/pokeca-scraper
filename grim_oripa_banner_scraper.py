import os
import time
import json
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# WordPress側の既存URL一覧取得API（プラグイン側で追加済み）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://grim-tcg.net-oripa.com"
TARGET_URL = BASE_URL

# -----------------------------
# WordPress既存URL取得
# -----------------------------
def fetch_existing_urls() -> set:
    print("🔍 WordPress既存URLを取得中...")
    try:
        res = requests.get(WP_GET_URL, auth=(WP_USER, WP_APP_PASS), timeout=30)
        if res.status_code != 200:
            print(f"⚠️ URL取得失敗: {res.status_code}")
            return set()
        urls = set(res.json())
        print(f"✅ 既存URL数: {len(urls)} 件")
        return urls
    except Exception as e:
        print(f"🛑 既存URL取得エラー: {e}")
        return set()

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_banners() -> list[dict]:
    print("🔍 grim-tcg.net-oripa.com バナー情報スクレイピング開始...")
    banners = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)
            slides = page.query_selector_all(".swiper-wrapper .swiper-slide")
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return banners

        for slide in slides:
            img = slide.query_selector("img")
            link = slide.query_selector("a")

            src = img.get_attribute("src") if img else ""
            href = link.get_attribute("href") if link else ""

            if not src:
                continue

            src = urljoin(BASE_URL, src)
            href = urljoin(BASE_URL, href) if href else TARGET_URL

            banners.append({
                "title": "バナーチャンネル",
                "image_url": src,
                "detail_url": href,
                "points": None,
                "price": None,
                "rarity": None,
                "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            })

        browser.close()

    print(f"✅ {len(banners)} 件のバナーを取得")
    return banners

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(banners, existing_urls):
    if not banners:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in banners:
        detail_url = item["detail_url"].strip()
        if detail_url in existing_urls or item["image_url"] in existing_urls:
            print(f"⏭ スキップ（重複）: {item['image_url']}")
            continue

        item["source_slug"] = "grim-tcg"
        new_items.append(item)

    if not new_items:
        print("📭 新規データなし（全件既存）")
        return

    print(f"🚀 新規 {len(new_items)}件をWordPressに送信中...")
    try:
        res = requests.post(WP_URL, json=new_items, auth=(WP_USER, WP_APP_PASS), timeout=60)
        print("Status:", res.status_code)
        try:
            print("Response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print("Response:", res.text)
    except Exception as e:
        print(f"🛑 WordPress送信中にエラー: {e}")

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    banners = scrape_banners()
    post_to_wordpress(banners, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
