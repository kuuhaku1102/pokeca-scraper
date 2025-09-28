import os
import base64
import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://ts-oripa.com"
TARGET_URL = "https://ts-oripa.com/"
SHEET_NAME = "その他"


def save_credentials() -> str:
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w", encoding="utf-8") as f:
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
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def fetch_existing_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 3:
            url = row[2].strip()
            if url:
                urls.add(normalize_url(url))
    return urls


def extract_list_items(page) -> List[Dict[str, str]]:
    js = """
    () => {
        const cards = document.querySelectorAll('div.cursor-pointer.w-full.overflow-hidden.rounded-xl.bg-gradient-to-br');
        return Array.from(cards, (card) => {
            const anchor = card.querySelector('a[href]');
            const img = card.querySelector('img');
            let image = '';
            if (img) {
                image = img.getAttribute('src') || img.getAttribute('data-src') || '';
            }
            return {
                url: anchor ? anchor.href : '',
                image,
            };
        });
    }
    """
    return page.evaluate(js)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_detail_info(page) -> Dict[str, str]:
    title = ""
    pt = ""

    title_selectors = [
        "h1",
        "h2",
        "div.text-2xl.font-bold",
        "div.text-xl.font-bold",
    ]
    for selector in title_selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                candidate = clean_text(locator.nth(0).inner_text())
                if candidate:
                    title = candidate
                    break
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    if not title:
        try:
            title = clean_text(page.title())
        except Exception:
            title = ""

    try:
        pt = page.evaluate(
            """
            () => {
                const patterns = [/([0-9,]+)\s*PT/i, /PT\s*[:：]\s*([0-9,]+)/i];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                while (walker.nextNode()) {
                    const el = walker.currentNode;
                    if (!el.textContent) continue;
                    const text = el.textContent.trim();
                    if (!text) continue;
                    for (const pattern of patterns) {
                        const match = text.match(pattern);
                        if (match) {
                            return match[1];
                        }
                    }
                }
                return '';
            }
            """
        )
    except Exception:
        pt = ""

    return {"title": title, "pt": pt}


def scrape_items(existing_urls: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        print("🔍 ts-oripa.com スクレイピング開始...")
        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector('div.cursor-pointer.w-full.overflow-hidden.rounded-xl.bg-gradient-to-br', timeout=60000)
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            html = page.content()
            with open('ts_oripa_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            browser.close()
            return rows

        items = extract_list_items(page)

        for item in items:
            detail_url = clean_text(item.get("url", ""))
            image_url = clean_text(item.get("image", ""))

            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            if image_url.startswith("/"):
                image_url = urljoin(BASE_URL, image_url)

            if not detail_url:
                continue

            norm_url = normalize_url(detail_url)
            if norm_url in existing_urls:
                print(f"⏭ スキップ（重複）: {detail_url}")
                continue

            detail_page = context.new_page()
            try:
                detail_page.goto(detail_url, timeout=60000, wait_until="domcontentloaded")
                detail_page.wait_for_timeout(1500)
                detail_info = extract_detail_info(detail_page)
            except Exception as exc:
                print(f"⚠️ 詳細ページ取得失敗: {detail_url} ({exc})")
                detail_info = {"title": "", "pt": ""}
            finally:
                detail_page.close()

            title = clean_text(detail_info.get("title", "")) or "noname"
            pt_raw = clean_text(detail_info.get("pt", ""))
            pt_value = re.sub(r"[^0-9]", "", pt_raw)

            rows.append([title, image_url, detail_url, pt_value])
            existing_urls.add(norm_url)

        browser.close()

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
