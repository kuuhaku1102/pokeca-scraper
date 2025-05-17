import os
import base64
from typing import List
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ====== 設定値 ======
BASE_URL = "https://japan-toreca.com/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")  # ← グローバルで取得

def save_credentials() -> str:
    """GSHEET_JSONをデコードして認証ファイルとして保存"""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
    """Googleスプレッドシートの 'その他' シートを返す"""
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    if not SPREADSHEET_URL:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)

def fetch_existing_urls(sheet) -> set:
    """既存URL（3列目）をsetで取得"""
    records = sheet.get_all_values()
    url_set = set()
    for row in records[1:]:
        if len(row) >= 3:
            url_set.add(row[2].strip())
    return url_set

def fetch_items(existing_urls: set) -> List[List[str]]:
    """japan-toreca TOPをPlaywrightでスクレイピングし、[タイトル,画像URL,詳細URL,PT]を返す"""
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 japan-toreca スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("img", timeout=60000)
        except Exception as e:
            print(f"🛑 ページ読み込み失敗: {e}")
            html = page.content()
            browser.close()
            with open("japan_toreca_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            return rows

        # 必要な情報をDOMから抽出（JS実行）
        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('[data-sentry-source-file="NewOripaCard.tsx"]').forEach(card => {
                    const link = card.closest('a') || card.querySelector('a[href]');
                    const img = card.querySelector('img');
                    if (!link || !img) return;
                    const title = (img.getAttribute('alt') || '').trim() || 'noname';
                    let image = img.getAttribute('src') || '';
                    const srcset = img.getAttribute('srcset');
                    if (srcset) {
                        const parts = srcset.split(',').map(s => s.trim().split(' ')[0]);
                        image = parts[parts.length - 1] || image;
                    }
                    let pt = '';
                    const span = card.querySelector('p span');
                    if (span) pt = span.textContent.trim();
                    results.push({ title, image, url: link.href, pt });
                });
                return results;
            }
            """
        )
        html = page.content()
        browser.close()

    # 新規アイテムを作成（重複除外）
    for item in items[:10]:
        detail_url = item.get("url", "")
        image_url = item.get("image", "")
        title = item.get("title", "") or "noname"
        pt_text = item.get("pt", "")

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title} ({detail_url})")
            continue

        print(f"✅ 取得: {title} ({detail_url})")
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)

    # デバッグ用HTML出力
    with open("japan_toreca_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    return rows

def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = fetch_items(existing_urls)
    print(f"rows（新規データ）: {rows}")  # デバッグ用出力
    if not rows:
        print("📭 新規データなし")
        return
    try:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    except Exception as e:
        print(f"❌ 書き込みエラー: {e}")

if __name__ == "__main__":
    main()
