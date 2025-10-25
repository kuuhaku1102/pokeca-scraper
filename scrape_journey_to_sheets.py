import os
import time
import json
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# WordPress 側の既存URL取得エンドポイント（プラグイン側で追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://journey-gacha.com/"
LIST_URL = urljoin(BASE_URL, "user/packList")

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
# 画像URLデコード関数
# -----------------------------
def decode_image_url(src: str) -> str:
    """Next.jsの_imageクエリ形式を通常URLに戻す"""
    if not src:
        return ""
    if src.startswith("/"):
        src = urljoin(BASE_URL, src)
    parsed = urlparse(src)
    qs = parse_qs(parsed.query)
    if "url" in qs and qs["url"]:
        return unquote(qs["url"][0])
    return src

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    print("🔍 journey-gacha.com スクレイピング開始...")
    items = []
    html = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(LIST_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector("div.packList__item", timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("journey_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return items

        items = page.evaluate(
            """
            () => {
                const arr = [];
                document.querySelectorAll('div.packList__item').forEach(el => {
                    arr.push({
                        id: el.getAttribute('data-pack-id') || '',
                        name: el.getAttribute('data-pack-name') || 'noname',
                        img: el.querySelector('img')?.getAttribute('src') || '',
                        pt: el.querySelector('p.packList__pt-txt')?.textContent || ''
                    });
                });
                return arr;
            }
            """
        )

        html = page.content()
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
        detail_url = urljoin(BASE_URL, f"pack/{item['id']}") if item['id'] else ""
        if not detail_url:
            continue
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item['name']}")
            continue

        image_url = decode_image_url(item.get("img", ""))
        pt_text = item.get("pt", "").replace(",", "").strip()
        title = item.get("name", "noname").strip() or "noname"

        new_items.append({
            "source_slug": "journey-gacha",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_text,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })
        existing_urls.add(detail_url)

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
