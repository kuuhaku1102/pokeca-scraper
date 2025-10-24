import os
import re
import time
import json
from urllib.parse import urljoin
from typing import List
import requests
from bs4 import BeautifulSoup

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象設定
# -----------------------------
BASE_URL = "https://iris-toreca.com/"
PACK_SELECTOR = "a.pack-content"
THUMBNAIL_SELECTOR = "div.pack-thumbnail img"
PRICE_SELECTOR = "div.pack-price-count i"
TITLE_SELECTOR = "h1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

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
# HTML取得ヘルパー
# -----------------------------
def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

# -----------------------------
# 価格抽出ロジック
# -----------------------------
def extract_pt(text: str) -> str:
    match = re.search(r"(\d+(?:,\d+)*)", text)
    return match.group(1) if match else ""

# -----------------------------
# タイトル取得（詳細ページ）
# -----------------------------
def fetch_title(detail_url: str) -> str:
    time.sleep(1)  # polite delay
    try:
        soup = fetch_page(detail_url)
    except Exception as exc:
        print(f"⚠ 詳細ページ読み込み失敗: {detail_url} ({exc})")
        return ""
    title_tag = soup.select_one(TITLE_SELECTOR)
    if title_tag:
        return title_tag.get_text(strip=True)
    if soup.title:
        return soup.title.get_text(strip=True)
    return ""

# -----------------------------
# メインスクレイピング処理
# -----------------------------
def scrape(existing_urls: set) -> List[dict]:
    print("🔍 iris-toreca.com スクレイピング開始...")
    soup = fetch_page(BASE_URL)
    results = []

    for a in soup.select(PACK_SELECTOR):
        img_tag = a.select_one(THUMBNAIL_SELECTOR)
        pt_tag = a.select_one(PRICE_SELECTOR)
        image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
        detail_url = a.get("href", "")
        pt_text = pt_tag.get_text(strip=True) if pt_tag else ""

        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)

        if not detail_url or detail_url in existing_urls:
            continue

        pt_value = extract_pt(pt_text)
        title = fetch_title(detail_url) or "noname"

        results.append({
            "source_slug": "iris-toreca",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_value,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })
    print(f"✅ {len(results)} 件のデータを取得完了")
    return results

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items: List[dict], existing_urls: set):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = [item for item in items if item["detail_url"] not in existing_urls]
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
    items = scrape(existing_urls)
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
