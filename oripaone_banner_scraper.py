import os
import base64

from playwright.sync_api import sync_playwright

TARGET_URL = "https://oripaone.jp"
OUTPUT_FILE = "debug_output.html"


def save_html():
    print("🌐 PlaywrightでページHTMLを取得・保存します...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)  # 読み込み安定化

            html = page.content()
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"✅ HTMLを保存しました: {OUTPUT_FILE}")

        except Exception as e:
            print(f"🛑 エラー発生: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    save_html()
