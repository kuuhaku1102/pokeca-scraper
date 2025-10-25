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
BASE_URL = "https://pokepa365.com"
INDEX_URL = f"{BASE_URL}/index"

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
# URL正規化（クエリ除去）
# -----------------------------
def strip_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

# -----------------------------
# スクレイピング関数
# -----------------------------
def parse_items(page) -> list[dict]:
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.series-item').forEach(item => {
                const a = item.querySelector('a.single-page');
                if (!a) return;
                const detail = a.getAttribute('link') || a.getAttribute('href') || '';
                const img = a.querySelector('div.bgimg img');
                const image = img ? (img.getAttribute('src') || '') : '';
                let title = '';
                if (img) title = img.getAttribute('alt') || '';
                const ptEl = item.querySelector('div.price span.valuetext');
                const pt = ptEl ? ptEl.textContent.trim() : '';
                results.push({title, image, url: detail, pt});
            });
            return results;
        }
        """
    )

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    print("🔍 pokepa365.com スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/114.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        try:
            page.goto(INDEX_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(8000)
            page.wait_for_selector("div.series-item", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("pokepa365_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return rows

        items = parse_items(page)
        browser.close()

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
        detail_url = item.get("url", "").strip()
        if not detail_url:
            continue
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        norm_url = strip_query(detail_url)

        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {detail_url}")
            continue

        image_url = item.get("image", "").strip()
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        title = item.get("title", "").strip() or "noname"
        pt_text = item.get("pt", "")
        pt_value = re.sub(r"[^0-9]", "", pt_text)

        new_items.append({
            "source_slug": "pokepa365",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_value,
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
    items = scrape_items()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
