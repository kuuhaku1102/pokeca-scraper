import os
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth
from playwright.sync_api import sync_playwright


# 対象サイト
BASE_URL = "https://ichica.co"
TARGET_URL = BASE_URL
SITE_NAME = "ichica"  # ← WordPress Banner Ingest に登録される値


# WordPress REST API (Banner Ingest プラグイン)
WP_BASE_URL = os.environ.get("WP_banar_BASE_URL")
WP_USER = os.environ.get("WP_banar_USER")
WP_APP_PASS = os.environ.get("WP_banar_APP_PASS")


def scrape_banners() -> list:
    """ichica のメイン画像をスクレイピング"""
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # ichica の画像は #testing 内に入っている
            images = page.query_selector_all("#testing img")

        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            browser.close()
            return rows

        for img in images:
            src = img.get_attribute("src")
            if not src:
                continue

            src = urljoin(BASE_URL, src)
            href = TARGET_URL  # リンク先はトップ固定

            rows.append({
                "site_name": SITE_NAME,
                "image_url": src,
                "link_url": href
            })

        browser.close()

    print(f"✅ {len(rows)} 件のバナーを取得")
    return rows


def send_to_wordpress(payload: list):
    """取得したバナーを WordPress Banner Ingest プラグインへ送信"""
    api_url = f"{WP_BASE_URL}/wp-json/banner/v1/ingest"

    print(f"📡 WordPress へ送信中: {api_url}")

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
        print(res.text)


def main():
    banners = scrape_banners()

    if not banners:
        print("📭 新規バナーなし（または取得失敗）")
        return

    send_to_wordpress(banners)


if __name__ == "__main__":
    main()
