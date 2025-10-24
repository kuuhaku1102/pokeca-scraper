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
BASE_URL = "https://dokkan-toreca.com/"

def scrape_dokkan() -> list:
    print("🔍 dokkan-toreca.com スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("li.chakra-wrap__listitem", timeout=60000)
        except Exception as e:
            html = page.content()
            with open("dokkan_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            notify_slack(f"🛑 ページ読み込み失敗: {e}")
            return items

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('li.chakra-wrap__listitem').forEach(li => {
                    const a = li.querySelector('a[href]');
                    if (!a) return;
                    const banner = a.querySelector('img[src*="banners"]');
                    const altText = banner ? banner.getAttribute('alt') || '' : '';
                    const textTitle = li.querySelector('div.css-3t04x3')?.textContent.trim() || '';
                    const title = altText && altText !== 'bannerImage' ? altText : textTitle;
                    const imgSrc = banner ? banner.src : '';
                    const detail = a.href;
                    const ptBox = li.querySelector('div.chakra-stack.css-1g48141');
                    let pt = '';
                    if (ptBox) pt = ptBox.textContent.replace(/\\s+/g, '');
                    results.push({title, image: imgSrc, url: detail, pt});
                });
                return results;
            }
            """
        )
        browser.close()
    print(f"✅ {len(items)} 件のデータ取得完了")
    return items

# -----------------------------
# WordPress REST API投稿（重複除外）
# -----------------------------
def post_to_wordpress(items: list, existing_urls: set):
    if not items:
        print("📭 投稿データなし")
        return

    new_items = []
    for item in items:
        detail_url = item.get("url", "").strip()
        if not detail_url:
            continue

        # 正規化
        parsed = urlparse(detail_url)
        norm_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item.get('title', 'noname')}")
            continue

        image_url = item.get("image", "")
        title = item.get("title", "").strip() or "noname"
        pt_text = re.sub(r"[^0-9,]", "", item.get("pt", ""))

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        new_items.append({
            "source_slug": "dokkan-toreca",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": pt_text,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

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
        notify_slack(f"🛑 WordPress送信中にエラー: {e}")
        print(f"🛑 WordPress送信中にエラー: {e}")

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    items = scrape_dokkan()
    post_to_wordpress(items, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        notify_slack(f"❌ スクリプトエラー: {exc}")
        raise
