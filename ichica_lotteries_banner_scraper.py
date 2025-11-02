import os
import re
import time
import json
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# 既存URL取得用
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://ichica.co"
TARGET_URL = "https://ichica.co/?tab=Lotteries&dds=recommended"

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
# URL正規化
# -----------------------------
def strip_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_banners() -> list[dict]:
    print("🔍 ichica.co スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)
            images = page.query_selector_all("#testing img")
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            html = page.content()
            with open("ichica_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        for img in images:
            src = img.get_attribute("src")
            if not src:
                continue
            src = urljoin(BASE_URL, src)
            rows.append({"image": src, "detail_url": TARGET_URL})

        browser.close()

    print(f"✅ {len(rows)} 件のデータ取得完了")
    return rows

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        detail_url = item.get("detail_url", "").strip()
        image_url = item.get("image", "").strip()
        if not image_url:
            continue

        norm_url = strip_query(image_url)
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {image_url}")
            continue

        title = os.path.basename(urlparse(image_url).path) or "noname"

        new_items.append({
            "source_slug": "ichica",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": None,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

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
    items = scrape_banners()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
