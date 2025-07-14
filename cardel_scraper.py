import os
import base64
import re
from typing import List
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://cardel.online/"
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
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not spreadsheet_url:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(spreadsheet_url)
    return spreadsheet.worksheet(SHEET_NAME)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 cardel.online スクレイピング開始...")

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("div[id$='-Wrap']", timeout=60000)

            # スクロール処理
            page.evaluate("""
                async () => {
                    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                    let lastHeight = 0;
                    let sameCount = 0;
                    for (let i = 0; i < 30; i++) {
                        window.scrollBy(0, window.innerHeight);
                        await delay(300);
                        const newHeight = document.body.scrollHeight;
                        if (newHeight === lastHeight) {
                            sameCount++;
                            if (sameCount > 5) break;
                        } else {
                            sameCount = 0;
                            lastHeight = newHeight;
                        }
                    }
                }
            """)
            page.wait_for_timeout(2000)

            with open("cardel_debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())

        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows

        try:
            items = page.evaluate("""
                () => {
                    const results = [];
                    const elements = document.querySelectorAll('div[id$="-Wrap"]');
                    elements.forEach(el => {
                        const title = el.getAttribute('title') || '';
                        const fig = el.querySelector('figure');
                        let image = '';
                        if (fig) {
                            const img = fig.querySelector('img[src]');
                            if (img) {
                                image = img.src;
                            } else {
                                const bg = fig.style.backgroundImage || '';
                                const m = bg.match(/url\\((?:"|')?(.*?)(?:"|')?\\)/);
                                if (m) image = m[1];
                            }
                        }

                        let url = '';
                        const a = el.querySelector('a[href]');
                        if (a) {
                            url = a.href;
                        } else if (el.dataset && el.dataset.href) {
                            url = el.dataset.href;
                        } else {
                            const dh = el.getAttribute('data-href') || '';
                            if (dh) url = dh;
                            const oc = el.getAttribute('onclick');
                            if (!url && oc) {
                                const m = oc.match(/location\\.href=['"](.*?)['"]/);
                                if (m) url = m[1];
                            }
                        }
                        if (url && url.startsWith('/')) {
                            url = 'https://cardel.online' + url;
                        }

                        let pt = '';
                        const ptEl = el.querySelector('div.flex.justify-end p.text-sm');
                        if (ptEl) pt = ptEl.textContent.trim();
                        if (!pt) {
                            const txt = el.innerText;
                            const m = txt.match(/([0-9,]+)\\s*pt/);
                            if (m) pt = m[1];
                        }

                        results.push({ title, image, url, pt });
                    });
                    return results;
                }
            """)
            print(f"📦 要素数: {len(items)}")

        except Exception as e:
            print("🛑 evaluate中に失敗:", e)
            items = []

        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        if not detail_url:
            continue

        norm_url = normalize_url(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ スキップ（重複）: {item.get('title', '')}")
            continue

        image_url = item.get("image", "")
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        title = item.get("title", "").strip() or "noname"
        pt_text = re.sub(r"[^0-9]", "", item.get("pt", ""))

        rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(norm_url)
        print(f"✅ 取得: {title}")

    return rows


def main() -> None:
    sheet = get_sheet()
    existing_urls = fetch_existing_urls(sheet)
    rows = scrape_items(existing_urls)
    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(rows)} 件追記完了")
    else:
        print("📭 新規データなし")


if __name__ == "__main__":
    main()
