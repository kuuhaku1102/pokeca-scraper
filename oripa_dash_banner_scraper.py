import os
import time
import pymysql
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# -----------------------------
# 環境変数から DB 接続設定を読み込む
# -----------------------------
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_PORT = int(os.environ.get("DB_PORT", 3306))

# -----------------------------
# スクレイピング対象設定
# -----------------------------
BASE_URL = "https://oripa-dash.com"
TARGET_URL = "https://oripa-dash.com/user/packList"

# -----------------------------
# MySQL に保存
# -----------------------------
def save_to_db(rows):
    if not rows:
        print("📭 DB更新なし（新規データなし）")
        return

    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cur:
            # テーブルがなければ作成
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wp_scrapes (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255),
                    image_url TEXT,
                    detail_url TEXT,
                    pt VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_url (detail_url(255))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            sql = """
                INSERT INTO wp_scrapes (title, image_url, detail_url, pt)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  title=VALUES(title),
                  image_url=VALUES(image_url),
                  pt=VALUES(pt),
                  created_at=CURRENT_TIMESTAMP
            """
            cur.executemany(sql, rows)
        conn.commit()
        print(f"💾 DBに {len(rows)} 件のデータを登録しました。")
    finally:
        conn.close()

# -----------------------------
# Playwright でスクレイピング
# -----------------------------
def scrape_dash():
    print("🔍 oripa-dash.com からデータ取得を開始します...")
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="load")
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            browser.close()
            return rows

        # 各オリパ情報を取得
        items = page.query_selector_all(".packList__item")
        print(f"📦 {len(items)} 件のアイテムを検出")

        for item in items:
            title = item.get_attribute("data-pack-name") or ""
            pack_id = item.get_attribute("data-pack-id") or ""
            img_tag = item.query_selector("img.packList__item-thumbnail")
            img_url = img_tag.get_attribute("src") if img_tag else ""
            if img_url.startswith("/"):
                img_url = urljoin(BASE_URL, img_url)

            pt_tag = item.query_selector(".packList__pt-txt")
            pt_text = pt_tag.inner_text().strip() if pt_tag else ""

            detail_url = f"{BASE_URL}/user/itemDetail?id={pack_id}" if pack_id else TARGET_URL
            rows.append([title, img_url, detail_url, pt_text])

        browser.close()
    print(f"✅ {len(rows)} 件のデータを取得完了")
    return rows

# -----------------------------
# メイン処理
# -----------------------------
def main():
    start = time.time()
    rows = scrape_dash()
    if not rows:
        print("📭 新しいデータはありません。")
        return
    save_to_db(rows)
    print(f"🏁 完了！処理時間: {round(time.time() - start, 2)} 秒")

if __name__ == "__main__":
    main()
