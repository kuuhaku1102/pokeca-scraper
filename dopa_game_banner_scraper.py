import os
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
from playwright.sync_api import sync_playwright


BASE_URL = "https://dopa-game.jp"
TARGET_URL = BASE_URL
SITE_NAME = "dopa"  # ← バナー登録時の site_name として送信


# ▼ WordPress REST API（Banner Ingest プラグイン）接続情報
WP_BASE_URL = os.environ.get("WP_banar_BASE_URL")      # 例: https://example.com
WP_USER     = os.environ.get("WP_banar_USER")          # WordPressユーザー名
WP_APP_PASS = os.environ.get("WP_banar_APP_PASS")      # アプリケーションパスワード


def scrape_banners() -> list:
    """Playwright でバナー画像をスクレイピングして返す"""
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/114.0.0.0 Safari/537.36"
            )
        )

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(8000)
            slides = page.query_selector_all(".slick-slide")
        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            browser.close()
            return rows

        for slide in slides:
            img = slide.query_selector("img")
            if not img:
                continue

            src = img.get_attribute("src") or ""
            if not src:
                continue

            src = urljoin(BASE_URL, src)
            href = BASE_URL  # dopa はリンク固定

            rows.append({
                "site_name": SITE_NAME,
                "image_url": src,
                "link_url": href,
            })

        browser.close()

    print(f"✅ {len(rows)} 件のバナー取得")
    return rows


def send_to_wordpress(payload: list):
    """Banner Ingest プラグインに登録 API を送信"""
    api_url = f"{WP_BASE_URL}/wp-json/banner/v1/ingest"

    print(f"📡 WordPress に送信開始: {api_url}")

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
        print("📭 新規バナーなし（または取得不能）")
        return

    # WordPress REST API へ送信
    send_to_wordpress(banners)


if __name__ == "__main__":
    main()
