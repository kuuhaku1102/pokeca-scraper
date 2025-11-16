import os
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from requests.auth import HTTPBasicAuth
from playwright.sync_api import sync_playwright


BASE_URL = "https://oripa.clove.jp"
TARGET_URL = f"{BASE_URL}/oripa/Pokemon"
SITE_NAME = "clove"  # ← WordPressに送信する site_name

# WordPress REST API 情報（Banner Ingest プラグイン）
WP_BASE_URL = os.environ.get("WP_banar_BASE_URL")
WP_USER = os.environ.get("WP_banar_USER")
WP_APP_PASS = os.environ.get("WP_banar_APP_PASS")


def decode_next_image(url: str) -> str:
    """Next.js の /_next/image?url=... を元画像URLに変換"""
    if url.startswith("/_next/image") and "url=" in url:
        query = parse_qs(urlparse(url).query).get("url")
        if query:
            return unquote(query[0])
    return url


def scrape_banners() -> list:
    print("🔍 Playwright によるスクレイピング開始...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/114.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)

            # スライダーをできるだけ進めて、画像を最大取得
            for _ in range(10):
                next_btn = page.query_selector(".swiper-button-next")
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_timeout(400)

            page.wait_for_selector(".swiper-slide img", timeout=10000)
            images = page.query_selector_all(".swiper-slide img")

        except Exception as e:
            print(f"🛑 読み込み失敗: {e}")
            context.close()
            browser.close()
            return rows

        print(f"🖼️ 検出された画像数: {len(images)}")

        for img in images:
            src = (
                img.get_attribute("src")
                or img.get_attribute("data-src")
                or img.get_attribute("data-lazy")
            )
            if not src:
                continue

            src = decode_next_image(src)

            if src.startswith("/"):
                src = urljoin(BASE_URL, src)

            rows.append({
                "site_name": SITE_NAME,
                "image_url": src,
                "link_url": TARGET_URL
            })

        context.close()
        browser.close()

    print(f"✅ 取得バナー数: {len(rows)}")
    return rows


def send_to_wordpress(payload: list):
    """取得したバナーを WordPress Banner Ingest プラグインへ送信"""
    api_url = f"{WP_BASE_URL}/wp-json/banner/v1/ingest"

    print("📡 WordPress に送信中...")

    res = requests.post(
        api_url,
        json=payload,
        auth=HTTPBasicAuth(WP_USER, WP_APP_PASS),
        timeout=30
    )

    print("📬 ステータス:", res.status_code)
    try:
        print("📦 レスポンス:", res.json())
    except:
        print("レスポンス:", res.text)


def main():
    banners = scrape_banners()

    if not banners:
        print("📭 新規バナーなし（または取得できず）")
        return

    # WordPress REST API へ送信
    send_to_wordpress(banners)


if __name__ == "__main__":
    main()
