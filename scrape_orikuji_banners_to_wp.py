import os
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth
from playwright.sync_api import sync_playwright

# 対象サイト
BASE_URL = "https://orikuji.com"
TARGET_URL = BASE_URL
SITE_NAME = "orikuji"  # ← WordPress 登録用 site_name

# WordPress Banner Ingest REST API 情報
WP_BASE_URL = os.environ.get("WP_banar_BASE_URL")
WP_USER = os.environ.get("WP_banar_USER")
WP_APP_PASS = os.environ.get("WP_banar_APP_PASS")


def scrape_banners() -> list:
    """おりくじのトップページからバナーを取得"""
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # カルーセル内の画像とリンクを取得
            slides = page.query_selector_all("section.carousel li.carousel__slide")

        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            browser.close()
            return rows

        for slide in slides:
            img = slide.query_selector("img")
            link = slide.query_selector("a")

            src = img.get_attribute("src") if img else ""
            href = link.get_attribute("href") if link else ""

            if not src:
                continue

            src = urljoin(BASE_URL, src)
            href = urljoin(BASE_URL, href) if href else TARGET_URL

            rows.append({
                "site_name": SITE_NAME,
                "image_url": src,
                "link_url": href
            })

        browser.close()

    print(f"✅ {len(rows)} 件のバナーを取得")
    return rows


def send_to_wordpress(payload: list):
    """WordPress Banner Ingest プラグインに送信"""
    api_url = f"{WP_BASE_URL}/wp-json/banner/v1/ingest"

    print("📡 WordPress へ送信開始...")

    res = requests.post(
        api_url,
        json=payload,
        auth=HTTPBasicAuth(WP_USER, WP_APP_PASS),
        timeout=30,
    )

    print("📬 ステータス:", res.status_code)
    try:
        print("📦 レスポンス:", res.json())
    except:
        print("レスポンス:", res.text)


def main():
    banners = scrape_banners()

    if not banners:
        print("📭 新規バナーなし（または取得失敗）")
        return

    send_to_wordpress(banners)


if __name__ == "__main__":
    main()
