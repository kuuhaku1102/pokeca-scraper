import os
import time
import json
from typing import List
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# WordPress 側に追加した GET エンドポイント（既存URL一覧）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://oripa.ex-toreca.com/"

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
# スクレイピング関数
# -----------------------------
def fetch_items_playwright() -> List[dict]:
    print("🔍 oripa.ex-toreca.com スクレイピング開始...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector("div.group.relative.cursor-pointer.rounded", timeout=10000)

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.group.relative.cursor-pointer.rounded').forEach(box => {
                    const img = box.querySelector('img');
                    const title = img ? (img.getAttribute('alt') || '').trim() : '';
                    const safe_title = title ? title : 'noname';
                    const image = img ? img.getAttribute('src') : '';

                    // 詳細URLを推測生成
                    let detail_url = '';
                    if (img) {
                        const src = img.getAttribute('src') || '';
                        const m = src.match(/original-pack\\/(\\d+)\\//);
                        if (m) {
                            detail_url = `https://oripa.ex-toreca.com/pack/${m[1]}`;
                        }
                    }

                    // pt抽出
                    let pt = '';
                    const ptEl = box.querySelector('p span');
                    if (ptEl) pt = ptEl.textContent.trim();

                    results.push({
                        title: safe_title,
                        image: image,
                        url: detail_url,
                        pt: pt
                    });
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

    # 既存URLを除外
    new_items = []
    for item in items:
        title = item.get("title", "noname")
        image_url = item.get("image", "")
        detail_url = item.get("url", "")
        pt_text = item.get("pt", "")

        if not detail_url:
            continue
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        # URL補正
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        new_items.append({
            "source_slug": "oripa-ex-toreca",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_text,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

    if not new_items:
        print("📭 新規データなし（全件重複）")
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
    items = fetch_items_playwright()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
