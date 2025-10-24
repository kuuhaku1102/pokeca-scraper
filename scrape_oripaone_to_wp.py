import os
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests

# -----------------------------
# WordPress REST API設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

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
# スクレイピング処理
# -----------------------------
def scrape_oripaone():
    print("🔍 oripaone.jp スクレイピング開始...")
    driver.get("https://oripaone.jp/")

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.relative.overflow-hidden.bg-white.shadow"))
        )
    except:
        print("❌ 要素が読み込まれませんでした。")
        driver.quit()
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select("div.relative.overflow-hidden.bg-white.shadow")

    results = []
    for card in cards:
        a_tag = card.find("a", href=True)
        img_tag = card.find("img")

        if not a_tag or not img_tag:
            continue

        title = img_tag.get("alt") or "pack"
        image_url = img_tag.get("src")
        detail_url = "https://oripaone.jp" + a_tag["href"]

        # 価格抽出
        price_tag = card.select_one("p.text-xl.font-bold")
        price_text = ""
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            if "/1回" in price_text:
                price_text = price_text.replace("/1回", "").strip()

        results.append({
            "source_slug": "oripaone",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "price": re.sub(r"[^0-9]", "", price_text),
            "points": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")},
        })

    driver.quit()
    print(f"✅ 取得件数: {len(results)} 件")
    return results

# -----------------------------
# WordPress REST API投稿
# -----------------------------
def post_to_wordpress(items):
    if not items:
        print("📭 投稿データなし")
        return

    print(f"🚀 {len(items)}件をWordPressに送信中...")
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
    items = scrape_oripaone()
    post_to_wordpress(items)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
