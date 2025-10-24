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

# WordPress 側の既存URL一覧エンドポイント（プラグイン側に追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://ichica.co/"

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
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    print("🔍 ichica.co スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=120000)
            page.wait_for_timeout(7000)
            cards = page.query_selector_all('div.clickable-element.bubble-element.Group.cmgaAm')
            print(f"🟢 検出数: {len(cards)}")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open("ichica_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            return items

        for card in cards:
            img = card.query_selector('div.bubble-element.Image.cmgaBaP img')
            image_url = img.get_attribute('src') if img else ""
            title = img.get_attribute('alt') if (img and img.get_attribute('alt')) else (image_url.split("/")[-1] if image_url else "noname")

            pt_el = card.query_selector('div.bubble-element.Text.cmgaAy')
            pt = pt_el.inner_text().strip() if pt_el else ""

            progress_div = card.query_selector('div.progress-bar')
            detail_id = None
            if progress_div:
                progress_id = progress_div.get_attribute('id')
                m = re.search(r'dynamic-progress-bar([0-9a-z]+)', progress_id or "")
                if m:
                    detail_id = m.group(1)

            detail_url = (
                f"https://ichica.co/pack/{detail_id}?section=main%20list&sort=recommended&category=Pokemon&lotteryprice=&lotterycard={detail_id}&lotterytab=all"
                if detail_id else ""
            )

            if not (title and image_url and detail_url):
                continue

            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            items.append({
                "source_slug": "ichica-main",
                "title": title,
                "image_url": image_url,
                "detail_url": detail_url,
                "points": pt,
                "price": None,
                "rarity": None,
                "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            })

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

    new_items = []
    for item in items:
        detail_url = item.get("detail_url", "").strip()
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item['title']}")
            continue
        new_items.append(item)

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
    scraped_items = scrape_items()
    post_to_wordpress(scraped_items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
