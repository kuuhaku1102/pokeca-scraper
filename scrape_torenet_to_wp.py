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

# WordPress側の既存URL取得エンドポイント（プラグインで追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://torenet.com"
TARGET_URL = "https://torenet.com/user/packList"

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
def scrape_torenet() -> List[dict]:
    print("🔍 torenet.com スクレイピング開始...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(TARGET_URL, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_selector(".packList__item", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return []

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('.packList__item').forEach(item => {
                    const title = item.getAttribute('data-pack-name') || 'noname';
                    let image = '';
                    const img = item.querySelector('img');
                    if (img) {
                        const srcset = img.getAttribute('srcset');
                        if (srcset) {
                            const parts = srcset.split(',').map(p => p.trim().split(' ')[0]);
                            if (parts.length) image = parts[parts.length - 1];
                        } else {
                            image = img.getAttribute('src') || '';
                        }
                    }
                    const packId = item.getAttribute('data-pack-id');
                    let url = '';
                    if (packId) url = `/pack/${packId}`;

                    let pt = '';
                    const ptEl = item.querySelector('.packList__pt-txt');
                    if (ptEl) {
                        const text = ptEl.textContent.replace(/,/g, '').trim();
                        const m = text.match(/(\\d+)/);
                        if (m) pt = m[1];
                    }
                    results.push({ title, image, url, pt });
                });
                return results;
            }
            """
        )
        browser.close()
    print(f"✅ {len(items)} 件のデータを取得完了")
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
        title = item.get("title", "noname").strip()
        image_url = item.get("image", "").strip()
        detail_url = item.get("url", "").strip()
        pt = item.get("pt", "").strip()

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        new_items.append({
            "source_slug": "torenet",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt,
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
        print("🛑 WordPress送信中にエラー:", e)

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    items = scrape_torenet()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
