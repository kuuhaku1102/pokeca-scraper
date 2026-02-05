import os
import time
import json
import re
from typing import List, Dict
from urllib.parse import urljoin

import requests
from playwright.sync_api import sync_playwright

# =============================
# WordPress REST API 設定
# =============================
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_GET_URL = os.getenv("WP_GET_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/list"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# =============================
# スクレイピング対象
# =============================
BASE_URL = "https://www.novagacha.com"
TARGET_URL = "https://www.novagacha.com/?tab=gacha&category=2"

# =============================
# 既存URL取得（WordPress）
# =============================
def fetch_existing_urls() -> set:
    print("🔍 WordPress既存URLを取得中...")
    try:
        res = requests.get(
            WP_GET_URL,
            auth=(WP_USER, WP_APP_PASS),
            timeout=30
        )
        if res.status_code != 200:
            print(f"⚠️ 既存URL取得失敗: {res.status_code}")
            return set()
        urls = set(res.json())
        print(f"✅ 既存URL数: {len(urls)} 件")
        return urls
    except Exception as e:
        print(f"🛑 既存URL取得エラー: {e}")
        return set()

# =============================
# ページ内データ抽出
# =============================
def parse_items(page) -> List[Dict]:
    js = """
    () => {
        const results = [];
        document.querySelectorAll('section.flex.flex-col.px-1').forEach(sec => {
            const link = sec.querySelector('a[href]');
            if (!link) return;

            const url = link.href;

            // 画像URL（background-image）
            let image = '';
            const bgDiv = sec.querySelector("div.bg-cover");
            if (bgDiv) {
                const match = /url\\(["']?(.*?)["']?\\)/.exec(bgDiv.style.backgroundImage);
                if (match) image = match[1];
            }

            // ポイント
            let pt = '';
            const ptEl = sec.querySelector("div.text-xl");
            if (ptEl) pt = ptEl.textContent.trim();

            const title = "noname"; // 現状HTMLに明示的なタイトルなし

            results.push({ title, image, url, pt });
        });
        return results;
    }
    """
    return page.evaluate(js)

# =============================
# スクレイピング本体
# =============================
def scrape_novagacha() -> List[Dict]:
    print("🔍 novagacha.com スクレイピング開始...")
    items: List[Dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("section.flex.flex-col.px-1", timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return items

        raw_items = parse_items(page)
        browser.close()

    for item in raw_items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip()
        pt_text = item.get("pt", "")
        points = re.sub(r"[^0-9]", "", pt_text)

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if not detail_url:
            continue

        items.append({
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": points
        })

    print(f"✅ {len(items)} 件のデータ取得完了")
    return items

# =============================
# WordPressへ投稿（upsert）
# =============================
def post_to_wordpress(items: List[Dict], existing_urls: set):
    if not items:
        print("📭 投稿データなし")
        return

    payload = []

    for item in items:
        detail_url = item["detail_url"]
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {detail_url}")
            continue

        payload.append({
            "source_slug": "novagacha",
            "title": item["title"],
            "image_url": item["image_url"],
            "detail_url": detail_url,
            "points": item["points"],
            "price": None,
            "rarity": None,
            "extra": {
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    if not payload:
        print("📭 新規データなし（全件既存）")
        return

    print(f"🚀 新規 {len(payload)} 件をWordPressへ送信中...")
    try:
        res = requests.post(
            WP_URL,
            json=payload,
            auth=(WP_USER, WP_APP_PASS),
            timeout=60
        )
        print("Status:", res.status_code)
        try:
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(res.text)
    except Exception as e:
        print("🛑 投稿エラー:", e)

# =============================
# メイン処理
# =============================
def main():
    start = time.time()

    existing_urls = fetch_existing_urls()
    scraped_items = scrape_novagacha()
    post_to_wordpress(scraped_items, existing_urls)

    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
