import os
import re
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# -----------------------------
# WordPress REST API設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# Selenium設定
# -----------------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,2000")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

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
# oripalette.jp スクレイピング
# -----------------------------
def scrape_oripalette():
    print("🔍 oripalette.jp スクレイピング開始...")
    driver.get("https://oripalette.jp/")

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.banner_base.banner"))
        )
    except Exception as e:
        print(f"❌ 要素が読み込まれませんでした: {e}")
        driver.quit()
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select("div.banner_base.banner")
    results = []

    for card in cards:
        a_tag = card.find("a", href=True)
        img_tag = card.find("img")
        point_tag = card.select_one(".point, .point_area, div.point")

        if not a_tag or not img_tag:
            continue

        title = img_tag.get("alt") or img_tag.get("title") or "pack"
        image_url = img_tag.get("data-src") or img_tag.get("src") or ""
        detail_url = a_tag["href"]

        if detail_url.startswith("/"):
            detail_url = "https://oripalette.jp" + detail_url
        if image_url.startswith("/"):
            image_url = "https://oripalette.jp" + image_url

        price = None
        if point_tag:
            m = re.search(r"(\d+)", point_tag.get_text().replace(",", ""))
            price = m.group(1) if m else None

        results.append({
            "source_slug": "oripalette",
            "title": title.strip(),
            "image_url": image_url.strip(),
            "detail_url": detail_url.strip(),
            "price": price,
            "points": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")},
        })

    driver.quit()
    print(f"✅ 取得件数: {len(results)} 件")
    return results

# -----------------------------
# WordPress投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
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
    items = scrape_oripalette()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
