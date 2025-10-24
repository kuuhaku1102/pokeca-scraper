import os
import time
import json
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://oripa-dash.com"
TARGET_URL = "https://oripa-dash.com/user/packList"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_dash():
    print("🔍 oripa-dash.com からデータ取得を開始します...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return rows

        items = page.query_selector_all(".packList__item")
        print(f"📦 {len(items)} 件のアイテムを検出")

        for item in items:
            title = item.get_attribute("data-pack-name") or ""
            pack_id = item.get_attribute("data-pack-id") or ""
            img_tag = item.query_selector("img.packList__item-thumbnail")
            img_url = img_tag.get_attribute("src") if img_tag else ""
            if img_url.startswith("/"):
                img_url = urljoin(BASE_URL, img_url)

            pt_tag = item.query_selector(".packList__pt-txt")
            pt_text = pt_tag.inner_text().strip() if pt_tag else ""

            detail_url = f"{BASE_URL}/user/itemDetail?id={pack_id}" if pack_id else TARGET_URL

            rows.append({
                "source_slug": "oripa-dash",
                "title": title,
                "image_url": img_url,
                "detail_url": detail_url,
                "price": None,
                "points": pt_text,
                "rarity": None,
                "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            })

        browser.close()

    print(f"✅ {len(rows)} 件のデータを取得完了")
    return rows

# -----------------------------
# WordPress REST API 送信
# -----------------------------
def post_to_wordpress(items):
    if not items:
        print("📭 投稿データなし")
        return

    print(f"🚀 {len(items)}件のデータをWordPressに送信します...")
    try:
        res = requests.post(WP_URL, json=items, auth=(WP_USER, WP_APP_PASS), timeout=60)
        print("Status:", res.status_code)
        try:
            print("Response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print("Response:", res.text)
    except Exception as e:
        print("🛑 WordPress送信中にエラー:", e)

# -----------------------------
# メイン
# -----------------------------
def main():
    start = time.time()
    items = scrape_dash()
    post_to_wordpress(items)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
