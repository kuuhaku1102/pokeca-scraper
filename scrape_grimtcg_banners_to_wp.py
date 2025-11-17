import os
import time
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
from playwright.sync_api import sync_playwright

# -----------------------------
# WordPress Banner Ingest API
# -----------------------------
WP_BASE_URL = os.environ.get("WP_banar_BASE_URL")
WP_USER = os.environ.get("WP_banar_USER")
WP_APP_PASS = os.environ.get("WP_banar_APP_PASS")
API_URL = f"{WP_BASE_URL}/wp-json/banner/v1/ingest"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://grim-tcg.net-oripa.com"
TARGET_URL = BASE_URL
SITE_NAME = "grim-tcg"   # ← WordPress で識別する site_name


def scrape_banners() -> list:
    """grim-tcg.net-oripa.com のバナーをスクレイピング"""
    print("🔍 grim-tcg バナー情報スクレイピング開始...")
    banners = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"]
        )
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # Swiper スライドの画像取得
            slides = page.query_selector_all(".swiper-wrapper .swiper-slide")

        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            browser.close()
            return banners

        for slide in slides:
            img = slide.query_selector("img")
            link = slide.query_selector("a")

            src = img.get_attribute("src") if img else ""
            href = link.get_attribute("href") if link else ""

            if not src:
                continue

            src = urljoin(BASE_URL, src)
            href = urljoin(BASE_URL, href) if href else TARGET_URL

            banners.append({
                "site_name": SITE_NAME,
                "image_url": src,
                "link_url": href,
            })

        browser.close()

    print(f"✅ {len(banners)} 件のバナーを取得")
    return banners


def post_to_wordpress(banners):
    """Banner Ingest プラグインへ送信"""
    if not banners:
        print("📭 投稿データなし")
        return

    print(f"🚀 {len(banners)} 件を WordPress へ送信中...")

    try:
        res = requests.post(
            API_URL,
            json=banners,
            auth=HTTPBasicAuth(WP_USER, WP_APP_PASS),
            timeout=60
        )

        print("📬 Status:", res.status_code)
        try:
            print("📦 Response:", res.json())
        except:
            print("Response:", res.text)

    except Exception as e:
        print(f"🛑 WordPress送信エラー: {e}")


def main():
    start = time.time()

    banners = scrape_banners()
    post_to_wordpress(banners)

    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")


if __name__ == "__main__":
    main()
