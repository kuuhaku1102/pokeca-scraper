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
BASE_URL = "https://moshoripa.com/"
INDEX_URL = "https://moshoripa.com/"

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
def strip_query_params(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    print("🔍 moshoripa.com スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            print(f"🌐 アクセス中: {INDEX_URL}")
            page.goto(INDEX_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div.homes-gacha-card", timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            html = page.content()
            with open("moshoripa_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return items

        print("📦 データ抽出中...")
        cards = page.evaluate(
            """
            () => {
                const data = [];
                const cards = document.querySelectorAll('div.homes-gacha-card');
                cards.forEach(card => {
                    const a = card.querySelector('a.gacha-link');
                    const detail_url = a ? a.href : '';
                    const img = card.querySelector('a.gacha-link > img');
                    const image_url = img ? img.src : '';
                    let title = a ? a.textContent.trim() : '';
                    if (!title || title.length < 2) {
                        title = img ? img.alt.trim() : 'No title';
                    }
                    const ptEl = card.querySelector('div.gacha-price span.font-size-xl');
                    const pt = ptEl ? ptEl.textContent.trim() : '0';
                    data.push({title, image_url, detail_url, pt});
                });
                return data;
            }
            """
        )

        for item in cards:
            detail_url = item.get("detail_url", "")
            image_url = item.get("image_url", "")
            title = item.get("title", "").strip() or "No title"
            pt_text = item.get("pt", "")
            pt_value = re.sub(r"[^0-9]", "", pt_text) or None

            if not detail_url:
                continue

            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            items.append({
                "title": title,
                "image_url": image_url,
                "detail_url": detail_url,
                "points": pt_value
            })

        browser.close()
        print(f"✅ {len(items)} 件のガチャ情報取得完了")

    return items

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        norm_url = strip_query_params(item["detail_url"])
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item['title']}")
            continue

        new_items.append({
            "source_slug": "moshoripa",
            "title": item["title"],
            "image_url": item["image_url"],
            "detail_url": item["detail_url"],
            "points": item["points"],
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

    if not new_items:
        print("📭 新規データなし（全件既存）")
        return

    print(f"🚀 新規 {len(new_items)} 件をWordPressに送信中...")
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
    items = scrape_items()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
