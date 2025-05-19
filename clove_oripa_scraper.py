import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse, unquote

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripa.clove.jp/oripa/All"
SHEET_NAME = "その他"

def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"

def get_sheet():
    creds_path = save_credentials()
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not spreadsheet_url:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(spreadsheet_url)
    return spreadsheet.worksheet(SHEET_NAME)

def normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("/"):
        url = urljoin("https://oripa.clove.jp", url)
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")

def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            u = row[2].strip()
            if u:
                norm = normalize_url(u)
                urls.add(norm)
    print("既存URLリスト:", urls)
    return urls

def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 oripa.clove.jp スクレイピング開始...")
        try:
            page.goto(BASE_URL, timeout=60000)
            page.wait_for_selector("div.css-k3cv9u", timeout=60000)
            html = page.content()
        except Exception as exc:
            print(f"🛑 ページ読み込みエラー: {exc}")
            html = page.content()
            browser.close()
            if html:
                with open("clove_oripa_page_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
            return rows

        items = page.evaluate(
            """
            () => {
                const results = [];
                document.querySelectorAll('div.css-k3cv9u').forEach(box => {
                    const img = box.querySelector('img');
                    const title = img ? (img.getAttribute('alt') || '').trim() : 'noname';
                    let img_src = img ? img.getAttribute('src') : '';
                    let image = img_src;
                    if (img_src && img_src.startsWith('/_next/image') && img_src.includes('url=')) {
                        const match = img_src.match(/url=([^&]+)/);
                        if (match) image = decodeURIComponent(match[1]);
                    }
                    // アイテムIDは画像URLから抜き出す
                    let itemId = "";
                    const m = image.match(/\\/items\\/([a-z0-9]+)\\.png/);
                    if (m) itemId = m[1];
                    // 詳細URL生成
                    let url = itemId ? `https://oripa.clove.jp/oripa/${itemId}` : "";
                    // ポイントや残数
                    let pt = "";
                    // コイン数など
                    const coinEl = box.querySelector('div.css-13pczcl p.chakra-text');
                    if (coinEl) pt = coinEl.textContent.trim();
                    // 残り個数
                    const leftEl = box.querySelector('p.chakra-text.css-m646o3');
                    let left = leftEl ? leftEl.textContent.trim() : '';
                    results.push({ title, image, url, pt, left });
                });
                return results;
            }
            """
        )
        browser.close()

    for item in items:
        title = item.get("title", "noname") or "noname"
        image_url = item.get("image", "")
        detail_url = item.get("url", "")
        pt_text = item.get("pt", "")
        left_text = item.get("left", "")

        detail_url = normalize_url(detail_url)
        if image_url and image_url.startswith("/"):
            image_url = urljoin("https://oripa.clove.jp", image_url)

        print(f"取得詳細URL: '{detail_url}'")
        if not detail_url or detail_url in [":", "https://oripa.clove.jp/oripa/All"]:
            print(f"⚠️ URLが空または異常: {title}")
            continue

        if detail_url in existing_urls:
            print(f"⏭ スキップ（重複）: {title} ({detail_url})")
            continue

        # 必要に応じて left_textも入れる: rows.append([title, image_url, detail_url, pt_text, left_text])
        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(detail_url)

    if html:
        with open("clove_oripa_page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
    return rows

def main() -> None:
    try:
        sheet = get_sheet()
    except Exception as exc:
        print(f"❌ シート取得失敗: {exc}")
        return

    try:
        existing_urls = fetch_existing_urls(sheet)
        rows = scrape_items(existing_urls)
        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"📥 {len(rows)} 件追記完了")
        else:
            print("📭 新規データなし")
    except Exception as exc:
        print(f"❌ エラー: {exc}")

if __name__ == "__main__":
    main()
