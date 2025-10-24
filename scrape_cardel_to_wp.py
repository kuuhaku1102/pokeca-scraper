import os
import re
import time
import json
from urllib.parse import urljoin, urlparse
from typing import List

import requests
from playwright.sync_api import sync_playwright

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://cardel.online/"

# -----------------------------
# スクレイピング本体
# -----------------------------
def scrape_cardel() -> List[dict]:
    print("🔍 cardel.online スクレイピング開始...")
    rows: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector("div[id$='-Wrap']", timeout=20000)

            # スクロールで全件ロード
            page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    for (let i = 0; i < 30; i++) {
                        window.scrollBy(0, window.innerHeight);
                        await delay(300);
                    }
                }
            """)
            page.wait_for_timeout(1000)

            elements = page.query_selector_all("div[id$='-Wrap']")
            print(f"📦 検出: {len(elements)}件")

            for idx, el in enumerate(elements):
                try:
                    title = el.get_attribute("title") or f"noname-{idx}"

                    # 画像取得
                    image_url = ""
                    img = el.query_selector("figure img")
                    if img:
                        image_url = (img.get_attribute("src") or "").strip()
                        if image_url.startswith("/"):
                            image_url = urljoin(BASE_URL, image_url)

                    # PT抽出
                    pt_text = ""
                    pt_el = el.query_selector("div.flex.justify-end p.text-sm")
                    if pt_el:
                        pt_text = pt_el.inner_text().strip()
                    else:
                        m = re.search(r"([0-9,]+)\\s*pt", el.inner_text())
                        if m:
                            pt_text = m.group(1)

                    # 詳細URL取得
                    el.scroll_into_view_if_needed()
                    el.click(timeout=10000)
                    page.wait_for_timeout(2000)
                    detail_url = page.url
                    if detail_url.startswith("/"):
                        detail_url = urljoin(BASE_URL, detail_url)

                    # 整形
                    rows.append({
                        "source_slug": "cardel-online",
                        "title": title,
                        "image_url": image_url,
                        "detail_url": detail_url,
                        "points": re.sub(r"[^0-9]", "", pt_text),
                        "price": None,
                        "rarity": None,
                        "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    })
                    print(f"✅ 取得: {title} - {detail_url}")

                    # 戻る
                    page.go_back(wait_until="domcontentloaded")
                    page.wait_for_timeout(800)
                except Exception as e:
                    print(f"⚠️ スキップ index={idx}: {e}")
                    page.go_back(wait_until="domcontentloaded")
                    page.wait_for_timeout(800)
                    continue

        except Exception as e:
            print("🛑 スクレイピング失敗:", e)
        browser.close()
    print(f"✅ 取得完了: {len(rows)} 件")
    return rows

# -----------------------------
# WordPress REST API 投稿
# -----------------------------
def post_to_wordpress(items: List[dict]):
    if not items:
        print("📭 投稿データなし")
        return

    print(f"🚀 {len(items)}件のデータをWordPressに送信中...")
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
# メイン処理
# -----------------------------
def main():
    start = time.time()
    data = scrape_cardel()
    post_to_wordpress(data)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
