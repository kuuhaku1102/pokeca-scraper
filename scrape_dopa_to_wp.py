import os
import time
import re
import json
from urllib.parse import urljoin
from typing import List
import requests
from playwright.sync_api import sync_playwright

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# --- 重複確認用エンドポイント ---
WP_GET_URL = "https://online-gacha-hack.com/wp-json/wp/v2/oripa-items?per_page=100"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://dopa-game.jp/"
GACHA_CONTAINER_SELECTOR = "div.css-1flrjkp"
GACHA_LINK_SELECTOR = "a.css-4g6ai3"
IMAGE_SELECTOR = "img.chakra-image"

# -----------------------------
# PT抽出ロジック
# -----------------------------
def extract_pt(text: str) -> str:
    """テキストから '123PT' などの数字を抽出"""
    m = re.search(r"(\d{2,}(?:,\d+)*)", text)
    return m.group(1) if m else ""

# -----------------------------
# WordPress既存URLの取得
# -----------------------------
def fetch_existing_urls() -> set:
    print("🔍 既存データ取得中（WordPress）...")
    urls = set()
    page = 1
    while True:
        try:
            res = requests.get(
                f"{WP_GET_URL}&page={page}",
                auth=(WP_USER, WP_APP_PASS),
                timeout=30
            )
            if res.status_code != 200:
                break
            data = res.json()
            if not data:
                break
            for item in data:
                # プラグインで detail_url がメタ情報として保存されている場合
                if "detail_url" in item:
                    urls.add(item["detail_url"])
            page += 1
        except Exception as e:
            print(f"⚠️ 既存URL取得中にエラー: {e}")
            break
    print(f"✅ 既存URL: {len(urls)} 件")
    return urls

# -----------------------------
# スクレイピング本体
# -----------------------------
def scrape_dopa() -> List[dict]:
    print("🔍 dopa-game.jp スクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector(GACHA_CONTAINER_SELECTOR, timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows

        anchors = page.query_selector_all(f"{GACHA_CONTAINER_SELECTOR} {GACHA_LINK_SELECTOR}")
        print(f"📦 検出したガチャ数: {len(anchors)}")

        for a in anchors:
            try:
                detail_url = a.get_attribute("href") or ""
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()

                img = a.query_selector(IMAGE_SELECTOR)
                image_url = ""
                title = "noname"
                if img:
                    image_url = (img.get_attribute("src") or "").strip()
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                    title = (img.get_attribute("alt") or "").strip() or title
                if not title:
                    txt = a.inner_text().strip()
                    if txt:
                        title = txt

                pt_value = ""
                parent_div = a.evaluate_handle("node => node.parentElement")
                if parent_div:
                    parent_text = parent_div.inner_text().replace("\n", " ")
                    pt_value = extract_pt(parent_text)
                if not pt_value:
                    grandparent_div = a.evaluate_handle("node => node.parentElement ? node.parentElement.parentElement : null")
                    if grandparent_div:
                        gp_text = grandparent_div.inner_text().replace("\n", " ")
                        pt_value = extract_pt(gp_text)

                rows.append({
                    "source_slug": "dopa-game",
                    "title": title,
                    "image_url": image_url,
                    "detail_url": detail_url,
                    "points": pt_value,
                    "price": None,
                    "rarity": None,
                    "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                })
            except Exception as exc:
                print(f"⚠ 取得スキップ: {exc}")
                continue

        browser.close()

    print(f"✅ {len(rows)} 件のデータを取得完了")
    return rows

# -----------------------------
# WordPress REST API 投稿
# -----------------------------
def post_to_wordpress(items: List[dict], existing_urls: set):
    new_items = [i for i in items if i["detail_url"] not in existing_urls]
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
    items = scrape_dopa()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
