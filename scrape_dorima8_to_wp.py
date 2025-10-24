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

# WordPress 側で既存URL一覧を取得するカスタムRESTルート（プラグイン側で追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://dorima8.com/"

# -----------------------------
# WordPress既存URL取得
# -----------------------------
def fetch_existing_urls() -> set:
    print("🔍 WordPress既存URLを取得中...")
    try:
        res = requests.get(WP_GET_URL, auth=(WP_USER, WP_APP_PASS), timeout=30)
        if res.status_code != 200:
            print(f"⚠️ 既存URL取得失敗: {res.status_code}")
            return set()
        urls = set(res.json())
        print(f"✅ 既存URL数: {len(urls)} 件")
        return urls
    except Exception as e:
        print(f"🛑 既存URL取得エラー: {e}")
        return set()

# -----------------------------
# URL正規化（クエリを除去）
# -----------------------------
def strip_query(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_dorima8() -> list[dict]:
    print("🔍 dorima8.com スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector('div.banner_base.banner', timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows

        # JS経由でカードデータを抽出
        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.banner_base.banner').forEach(box => {
                    const img = box.querySelector('img.current') || box.querySelector('img');
                    const image = img ? (img.getAttribute('src') || '') : '';
                    let title = '';
                    const nameEl = box.querySelector('.name_area-pack_name');
                    if (nameEl) title = nameEl.textContent.trim();
                    if (!title && img) title = (img.getAttribute('alt') || img.getAttribute('title') || '').trim();

                    let url = '';
                    const a = box.querySelector('a[href]') || box.closest('a[href]');
                    if (a) url = a.getAttribute('href') || '';
                    if (!url) {
                        const m = image.match(/\\/pack\\/(\\d+)/);
                        if (m) url = `/pack/${m[1]}`;
                    }

                    let pt = '';
                    const ptEl = box.querySelector('.point_area');
                    if (ptEl) {
                        const txt = ptEl.textContent.replace(/[\\s,]/g, '');
                        const m2 = txt.match(/(\\d+)/);
                        if (m2) pt = m2[1];
                    }
                    results.push({ title, image, url, pt });
                });
                return results;
            }
            """
        )

        browser.close()

    print(f"✅ {len(items)} 件のデータ取得完了")
    return items

# -----------------------------
# WordPress REST API 投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        title = item.get('title', 'noname').strip() or 'noname'
        image_url = item.get('image', '').strip()
        detail_url = item.get('url', '').strip()
        pt_text = item.get('pt', '').strip()

        if detail_url.startswith('/'):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith('/'):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = strip_query(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        new_items.append({
            "source_slug": "dorima8",
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
        print("🛑 WordPress送信中にエラー:", e)

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    items = scrape_dorima8()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == '__main__':
    main()
