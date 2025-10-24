import os
import re
import time
import json
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# Slack通知
# -----------------------------
def notify_slack(message: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print(message)
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as exc:
        print(f"⚠️ Slack通知失敗: {exc}")
        print(message)

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
# スクレイピング処理
# -----------------------------
BASE_URL = "https://koppepanchi.com/"

def scrape_koppepanchi() -> list:
    print("🔍 koppepanchi.com スクレイピング開始...")
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector("div.relative.bg-white.rounded-lg.shadow-sm", timeout=60000)
        except Exception as exc:
            html = page.content()
            with open("koppepanchi_debug.html", "w", encoding="utf-8") as fh:
                fh.write(html)
            browser.close()
            notify_slack(f"🛑 koppepanchi ページ読み込み失敗: {exc}")
            return results

        items = page.evaluate(
            """
            () => {
                const cards = Array.from(
                    document.querySelectorAll('div.relative.bg-white.rounded-lg.shadow-sm')
                );
                return cards.map(card => {
                    const img = card.querySelector('img');
                    const title = (img?.getAttribute('alt') || '').trim() ||
                        (card.querySelector('h3, h2, p, span')?.textContent.trim() || '');
                    let image = '';
                    if (img) {
                        image = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    }
                    let url = '';
                    const link = card.querySelector('a[href]');
                    if (link) {
                        url = link.href;
                    } else {
                        const parentLink = card.closest('a[href]');
                        if (parentLink) url = parentLink.href;
                    }
                    if (!url) {
                        const button = card.querySelector('button[data-url], button[data-href]');
                        if (button) url = button.getAttribute('data-url') || button.getAttribute('data-href') || '';
                    }
                    if (!url) {
                        const datasetUrl = card.getAttribute('data-url') || card.getAttribute('data-href');
                        if (datasetUrl) url = datasetUrl;
                    }
                    let pt = '';
                    const ptBlocks = card.querySelectorAll('span.px-1.vc_module__point-raw');
                    if (ptBlocks.length) {
                        pt = Array.from(ptBlocks)[ptBlocks.length - 1].textContent.replace(/\\s+/g, '');
                    }
                    return { title, image, url, pt };
                }).filter(item => item.image || item.url || item.title);
            }
            """
        )

        browser.close()
        print(f"📦 {len(items)} 件のカードを取得")
        return items

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        title = item.get("title", "noname").strip()
        image_url = item.get("image", "").strip()
        detail_url = item.get("url", "").strip()
        pt_text = item.get("pt", "").strip()

        if not detail_url:
            print(f"⚠️ URLなしスキップ: {title}")
            continue

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        # 重複チェック
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        new_items.append({
            "source_slug": "koppepanchi",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": re.sub(r"[^0-9]", "", pt_text),
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

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
        notify_slack(f"🛑 WordPress送信中にエラー: {e}")
        print(f"🛑 WordPress送信中にエラー: {e}")

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    items = scrape_koppepanchi()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        notify_slack(f"❌ koppepanchi_scraper エラー: {exc}")
        raise
