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
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://kagura-tcg.com/"

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
def strip_query(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

# -----------------------------
# スクレイピング処理
# -----------------------------
def scrape_items() -> list[dict]:
    rows = []
    print("🔍 kagura-tcg.com スクレイピング開始...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            cards = page.query_selector_all("div.flex.flex-col.cursor-pointer")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            try:
                html = page.content()
                with open("kagura_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("💾 kagura_debug.html を保存しました")
            except Exception as e:
                print(f"⚠️ HTML保存失敗: {e}")
            browser.close()
            return rows

        print(f"📦 検出件数: {len(cards)}")

        for i in range(len(cards)):
            try:
                cards = page.query_selector_all("div.flex.flex-col.cursor-pointer")
                card = cards[i]

                # 画像URL取得
                image_url = ""
                try:
                    img_div = card.query_selector("div[style*='background-image']")
                    style = img_div.get_attribute("style") if img_div else ""
                    match = re.search(r'url\(["\']?(.*?)["\']?\)', style or "")
                    image_url = match.group(1) if match else ""
                    if image_url.startswith("/"):
                        image_url = urljoin(BASE_URL, image_url)
                except:
                    pass

                # 詳細ページ遷移
                with page.expect_navigation(wait_until="load", timeout=30000):
                    card.click()

                detail_url = page.url
                norm_url = strip_query(detail_url)
                if not norm_url:
                    print("⚠️ URLが空のためスキップ")
                    page.go_back()
                    continue

                # タイトル・価格取得
                title = "noname"
                try:
                    title = page.query_selector("h1").inner_text().strip()
                except:
                    pass

                pt_value = ""
                try:
                    pt_el = page.query_selector(".fa-coins")
                    pt_text = pt_el.evaluate("el => el.parentElement.textContent") if pt_el else ""
                    pt_value = re.sub(r"[^0-9]", "", pt_text)
                except:
                    pass

                rows.append({
                    "source_slug": "kagura-tcg",
                    "title": title,
                    "image_url": image_url,
                    "detail_url": detail_url,
                    "points": pt_value,
                    "price": None,
                    "rarity": None,
                    "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                })

                page.go_back()
                page.wait_for_timeout(1000)
                page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)

            except Exception as e:
                print(f"⚠️ アイテム処理失敗: {e}")
                try:
                    page.go_back()
                    page.wait_for_timeout(1000)
                    page.wait_for_selector("div.flex.flex-col.cursor-pointer", timeout=10000)
                except:
                    pass

        browser.close()
    print(f"✅ {len(rows)} 件のデータを取得完了")
    return rows

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        norm_url = strip_query(item["detail_url"])
        if norm_url in existing_urls:
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
