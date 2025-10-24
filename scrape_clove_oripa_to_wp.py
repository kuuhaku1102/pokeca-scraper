import os
import re
import time
import json
from urllib.parse import urljoin, urlparse, unquote
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# WordPress 側で既存URL一覧を取得するカスタムエンドポイント
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://oripa.clove.jp/oripa/All"

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
def scrape_clove_oripa():
    print("🔍 oripa.clove.jp スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000)
            page.wait_for_selector("div.css-k3cv9u", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込みエラー: {exc}")
            browser.close()
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.css-k3cv9u').forEach(box => {
                    const img = box.querySelector('img');
                    const title = img ? (img.getAttribute('alt') || '').trim() : 'noname';
                    let img_src = img ? img.getAttribute('src') : '';
                    let image = img_src;
                    if (img_src && img_src.startsWith('/_next/image') && img_src.includes('url=')) {
                        const match = img_src.match(/url=([^&]+)/);
                        if (match) image = decodeURIComponent(match[1]);
                    }
                    let itemId = "";
                    const m = image.match(/\\/items\\/([a-z0-9]+)\\.png/);
                    if (m) itemId = m[1];
                    let url = itemId ? `https://oripa.clove.jp/oripa/${itemId}` : "";
                    let pt = "";
                    const coinEl = box.querySelector('div.css-13pczcl p.chakra-text');
                    if (coinEl) pt = coinEl.textContent.trim();
                    const leftEl = box.querySelector('p.chakra-text.css-m646o3');
                    let left = leftEl ? leftEl.textContent.trim() : '';
                    results.push({ title, image, url, pt, left });
                });
                return results;
            }
            """
        )
        browser.close()

    print(f"✅ {len(items)} 件のデータを取得完了")
    return items

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    payload = []
    for item in items:
        title = item.get("title", "noname").strip()
        image_url = item.get("image", "").strip()
        detail_url = item.get("url", "").strip()
        points = item.get("pt", "").strip()

        # URL補正
        if detail_url.startswith("/"):
            detail_url = urljoin("https://oripa.clove.jp", detail_url)
        if image_url.startswith("/"):
            image_url = urljoin("https://oripa.clove.jp", image_url)

        # 重複スキップ
        if not detail_url or detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        payload.append({
            "source_slug": "oripa-clove",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": points,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

    if not payload:
        print("📭 新規データなし（全件重複）")
        return

    print(f"🚀 新規 {len(payload)}件をWordPressに送信中...")
    try:
        res = requests.post(WP_URL, json=payload, auth=(WP_USER, WP_APP_PASS), timeout=60)
        print("Status:", res.status_code)
        try:
            print("Response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print("Response:", res.text)
    except Exception as e:
        print("🛑 WordPress送信中にエラー:", e)

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    items = scrape_clove_oripa()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
