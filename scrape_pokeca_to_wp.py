import os
import time
import json
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# -----------------------------
# WordPress REST API設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

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
def scrape_pokeca() -> list:
    results = []
    print("🔍 pokeca.com スクレイピング開始...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        page_num = 1
        while True:
            try:
                url = f"https://pokeca.com/?page={page_num}"
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_selector("div.original-packs-card", timeout=60000)
            except Exception as e:
                print(f"🛑 ページ読み込みエラー: {str(e)}")
                html = page.content()
                with open(f"pokeca_error_page_{page_num}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                break

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.original-packs-card")

            # SOLDOUT検知
            if soup.select_one("div.soldout"):
                print("🏁 SOLDOUTが検出されました。スクレイピングを終了します。")
                break

            if not cards:
                print(f"🏁 ページ {page_num} でカードが見つかりませんでした。終了。")
                break

            for card in cards:
                a_tag = card.select_one("a.link-underline")
                img_tag = card.select_one("img.card-img-top")
                pt_tag = card.select_one("p.point-amount")

                if not (a_tag and img_tag and pt_tag):
                    continue

                title = img_tag.get("alt", "無題").strip()
                image_url = img_tag["src"]
                detail_url = a_tag["href"]
                pt_text = pt_tag.get_text(strip=True).replace("/1回", "").strip()

                if image_url.startswith("/"):
                    image_url = "https://pokeca.com" + image_url
                if detail_url.startswith("/"):
                    detail_url = "https://pokeca.com" + detail_url

                results.append({
                    "source_slug": "pokeca",
                    "title": title,
                    "image_url": image_url,
                    "detail_url": detail_url,
                    "points": re.sub(r"[^0-9]", "", pt_text),
                    "price": None,
                    "rarity": None,
                    "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                })

            print(f"📄 ページ {page_num} 完了")
            page_num += 1

        browser.close()
    print(f"✅ 取得完了: {len(results)} 件")
    return results

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
        if not detail_url or detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item.get('title', 'noname')}")
            continue
        new_items.append(item)

    if not new_items:
        print("📭 新規データなし（全件既存）")
        return

    print(f"🚀 新規 {len(new_items)}件をWordPressに送信中...")
    try:
        res = requests.post(WP_URL, json=new_items, auth=(WP_USER, WP_APP_PASS), timeout=90)
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
    items = scrape_pokeca()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
