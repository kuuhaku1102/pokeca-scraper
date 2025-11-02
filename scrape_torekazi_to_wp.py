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
BASE_URL = "https://torekazi.com/"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

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
# HTMLパース関数
# -----------------------------
def parse_items(page) -> list[dict]:
    """torekazi.com のトップページからガチャ情報を抽出"""
    return page.evaluate(
        """
        () => {
            const results = [];
            document.querySelectorAll('div.bg-white.rounded-lg').forEach(card => {
                const a = card.querySelector('a[href]');
                if (!a) return;
                const img = a.querySelector('img');
                const url = a.href;
                const image = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                const titleEl = card.querySelector('h2, h3, p.font-semibold, p.font-bold');
                let title = titleEl ? titleEl.textContent.trim() : '';
                if (!title && img) {
                    title = img.getAttribute('alt') || '';
                }
                const ptEl = card.querySelector('div.flex p.font-bold.text-lg');
                const pt = ptEl ? ptEl.textContent.replace(/\\s+/g, '') : '';
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
    print("🔍 torekazi.com スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=DEFAULT_UA)

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.bg-white.rounded-lg', timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("torekazi_debug.html", "w", encoding="utf-8") as f:
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
            "source_slug": "torekazi",
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
