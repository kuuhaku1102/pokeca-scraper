import os
import time
import json
from urllib.parse import urljoin
from typing import List
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# WordPress 側の既存URL取得API（プラグインに追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象設定
# -----------------------------
BASE_URL = "https://japan-toreca.com/"

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
def scrape_items() -> List[dict]:
    print("🔍 japan-toreca.com スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_selector('a[data-sentry-component="NewOripaCard"]', timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            html = page.content()
            with open("japan_toreca_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return items

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('a[data-sentry-component="NewOripaCard"]').forEach(card => {
                    const href = card.getAttribute('href') || '';
                    const img = card.querySelector('img');
                    if (!img) return;
                    const title = (img.getAttribute('alt') || '').trim() || 'noname';
                    let image = img.getAttribute('src') || '';
                    const srcset = img.getAttribute('srcset');
                    if (srcset) {
                        const parts = srcset.split(',').map(s => s.trim().split(' ')[0]);
                        image = parts[parts.length - 1] || image;
                    }
                    let pt = '';
                    const span = card.querySelector('span.css-1qwnwpn');
                    if (span) pt = span.textContent.trim();
                    results.push({ title, image, url: href, pt });
                });
                return results;
            }
            """
        )
        browser.close()

    print(f"✅ 取得件数: {len(items)} 件")
    return items

# -----------------------------
# WordPress REST API 投稿（重複除外）
# -----------------------------
def post_to_wordpress(items: List[dict], existing_urls: set):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        detail_url = item.get("url", "")
        image_url = item.get("image", "")
        title = item.get("title", "noname")
        pt_text = item.get("pt", "")

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        new_items.append({
            "source_slug": "japan-toreca",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_text,
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
