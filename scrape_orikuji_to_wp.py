import os
import time
import json
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import requests

# -----------------------------
# WordPress REST API 設定
# -----------------------------
WP_URL = os.getenv("WP_URL") or "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"
WP_USER = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")

# 既存URLを取得するカスタムRESTエンドポイント（プラグイン側に追加済み想定）
WP_GET_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/list"

# -----------------------------
# スクレイピング対象
# -----------------------------
BASE_URL = "https://orikuji.com/"
TARGET_URL = "https://orikuji.com/"

# -----------------------------
# 既存URL取得
# -----------------------------
def fetch_existing_urls() -> set:
    print("🔍 WordPress既存URLを取得中...")
    try:
        res = requests.get(WP_GET_URL, auth=(WP_USER, WP_APP_PASS), timeout=30)
        if res.status_code != 200:
            print(f"⚠️ 既存URL取得失敗: {res.status_code}")
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
def scrape_orikuji():
    print("🔍 orikuji.com スクレイピング開始...")
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector("div.white-box", timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return items

        # ページを下までスクロール（無限ロード対応）
        last_count = 0
        stable_loops = 0
        for _ in range(50):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)
            load_more = page.query_selector("button:has-text('もっと見る')")
            if load_more:
                load_more.click()
                page.wait_for_timeout(600)
            curr_count = len(page.query_selector_all("div.white-box"))
            if curr_count == last_count:
                stable_loops += 1
            else:
                stable_loops = 0
            last_count = curr_count
            if stable_loops >= 2:
                break
        print(f"👀 {last_count}件の white-box を検出")

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.white-box').forEach(box => {
                    const link = box.querySelector('a[href*="/gacha/"]');
                    const img = box.querySelector('div.image-container img');
                    if (!link || !img) return;
                    const imgSrc = img.getAttribute('data-src') || img.getAttribute('src') || '';
                    if (imgSrc.includes('/img/coin.png') || imgSrc.includes('/coin/lb_coin_')) return;

                    const title = img.getAttribute('alt') || 'noname';
                    const url = link.getAttribute('href') || '';
                    const ptEl = box.querySelector('span.coin-area');
                    const rawPt = ptEl ? ptEl.textContent : '';
                    const pt = rawPt.replace(/\\D/g, '');
                    results.push({ title, image: imgSrc, url, pt });
                });
                return results;
            }
            """
        )

        browser.close()

    print(f"✅ {len(items)} 件のデータ取得完了")
    return items

# -----------------------------
# WordPress REST API 投稿（重複除外）
# -----------------------------
def post_to_wordpress(items, existing_urls):
    if not items:
        print("📭 投稿データなし")
        return

    payload = []
    for item in items:
        title = item.get("title", "noname").strip()
        image_url = item.get("image", "").strip()
        detail_url = item.get("url", "").strip()
        points = item.get("pt", "").strip()

        # フルURL化
        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        # 重複チェック
        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        payload.append({
            "source_slug": "orikuji",
            "title": title,
            "image_url": image_url,
            "detail_url": detail_url,
            "points": points,
            "price": None,
            "rarity": None,
            "extra": {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        })

    if not payload:
        print("📭 新規データなし（全件既存）")
        return

    print(f"🚀 新規 {len(payload)}件のデータをWordPressに送信中...")
    try:
        res = requests.post(WP_URL, json=payload, auth=(WP_USER, WP_APP_PASS), timeout=60)
        print("Status:", res.status_code)
        try:
            print("Response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception:
            print("Response:", res.text)
    except Exception as e:
        print("🛑 送信エラー:", e)

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    existing_urls = fetch_existing_urls()
    scraped_data = scrape_orikuji()
    post_to_wordpress(scraped_data, existing_urls)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
