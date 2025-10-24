import os
import re
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

# 既存URL一覧取得用（プラグイン側に追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://eve-gacha.com/"

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
# スクレイピング処理
# -----------------------------
def scrape_eve_gacha() -> List[dict]:
    print("🔍 eve-gacha.com スクレイピング開始...")
    rows: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(BASE_URL, timeout=60000)
        page.wait_for_timeout(3000)

        cards = page.query_selector_all("a[href*='/gacha/']")
        print(f"取得したaタグ数: {len(cards)}")
        if len(cards) == 0:
            print("⚠️ 要素ゼロ → サイト構造変更の可能性")

        for a in cards:
            try:
                detail_url = a.get_attribute("href")
                if not detail_url:
                    continue
                if detail_url.startswith("/"):
                    detail_url = urljoin(BASE_URL, detail_url)
                detail_url = detail_url.strip()

                # --- カード情報 ---
                img = a.query_selector("img")
                image_url = ""
                title = "noname"
                if img:
                    image_url = img.get_attribute("data-src") or img.get_attribute("src") or ""
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                    image_url = image_url.strip()
                    alt = img.get_attribute("alt") or img.get_attribute("title")
                    if alt:
                        title = alt.strip() or title
                if title == "noname":
                    text = a.inner_text().strip()
                    if text:
                        title = text.split()[0]

                # --- PT（価格）抽出 ---
                pt = ""
                parent_card = a
                for _ in range(5):
                    tmp = parent_card.evaluate_handle("el => el.parentElement")
                    class_name = tmp.evaluate("el => el.className")
                    if isinstance(class_name, str) and (
                        "bg-yellow" in class_name or "border" in class_name or "shadow" in class_name
                    ):
                        parent_card = tmp
                        break
                    parent_card = tmp

                pt_elements = parent_card.query_selector_all("span.font-bold")
                pt_candidates = []
                for e in pt_elements:
                    t = e.inner_text().strip()
                    m = re.search(r"(\d{3,6})", t.replace(",", ""))
                    if m:
                        pt_candidates.append(m.group(1))
                if pt_candidates:
                    pt = pt_candidates[0]

                rows.append({
                    "source_slug": "eve-gacha",
                    "title": title,
                    "image_url": image_url,
                    "detail_url": detail_url,
                    "points": pt,
                    "price": None,
                    "rarity": None,
                    "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                })
            except Exception as exc:
                print(f"⚠️ 取得スキップ: {exc}")
                continue

        browser.close()

    print(f"✅ {len(rows)} 件のデータ取得完了")
    return rows

# -----------------------------
# WordPress REST API 投稿（重複除外）
# -----------------------------
def post_to_wordpress(items: List[dict], existing_urls: set):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = [item for item in items if item["detail_url"] not in existing_urls]
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
    items = scrape_eve_gacha()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
