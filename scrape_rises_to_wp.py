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
BASE_URL = "https://rises.jp/product"

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
def normalize_url(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"

# -----------------------------
# スクレイピング関数
# -----------------------------
def parse_items(page):
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.gacha-item').forEach(card => {
                const link = card.querySelector('a[href]');
                const img = link ? link.querySelector('img') : null;
                const url = link ? link.href : '';
                const image = img ? (img.getAttribute('src') || '') : '';
                const title = img ? (img.getAttribute('alt') || '').trim() : '';
                let pt = '';
                const span = card.querySelector('span.gacha-price');
                if (span) pt = span.textContent.replace(/\\s+/g, '');
                results.push({title, image, url, pt});
            });
            return results;
        }
        """
    )

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    print("🔍 rises.jp スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0 Safari/537.36"
            )
        )

        try:
            page.goto(BASE_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector("div.gacha-item", timeout=120000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("rises_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return items

        parsed = parse_items(page)
        browser.close()

    for item in parsed:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip() or "noname"
        pt_text = re.sub(r"[^0-9]", "", item.get("pt", "")) or None

        if detail_url.startswith("/"):
            detail_url = urljoin("https://rises.jp", detail_url)
        if image_url.startswith("/"):
            image_url = urljoin("https://rises.jp", image_url)

        items.append({
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_text
        })

    print(f"✅ {len(items)} 件のデータ取得完了")
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
        detail_url = item["detail_url"]
        norm_url = normalize_url(detail_url)
        if not detail_url or norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item['title']}")
            continue

        new_items.append({
            "source_slug": "risesjp",
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
