"""Scraper for koppepanchi.com using Playwright.

This script collects gacha information (title, image URL, detail URL, PT)
from https://koppepanchi.com/ and appends new entries to the 指定 Google
Spreadsheet sheet named "その他". Duplicate detail URLs are skipped.
"""

from __future__ import annotations

import base64
import os
import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import gspread
import requests
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

BASE_URL = "https://koppepanchi.com/"
SHEET_NAME = "その他"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")
DEBUG_HTML = "koppepanchi_debug.html"


def notify_slack(message: str) -> None:
    """Send a message to Slack if a webhook URL is configured."""

    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print(message)
        return

    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as exc:  # pragma: no cover - best effort notification
        print(f"Slack notification failed: {exc}")
        print(message)


def save_credentials() -> str:
    """Persist Google service account credentials from the environment."""

    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w", encoding="utf-8") as fh:
        fh.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return the Google Sheets worksheet for appending scraped rows."""

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


def strip_query(url: str) -> str:
    """Remove query strings when comparing URLs for duplicates."""

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def normalise_pt(raw: str) -> str:
    """Extract the numeric PT portion and format as `<value>PT` if possible."""

    compact = raw.replace("\n", "").strip()
    if not compact:
        return ""
    match = re.search(r"(\d[\d,]*)", compact)
    if not match:
        return compact
    number = match.group(1)
    return f"{number}PT"


def fetch_items() -> List[Dict[str, str]]:
    """Scrape koppepanchi cards via Playwright and return raw dictionaries."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 koppepanchi スクレイピング開始…")
        try:
            page.goto(BASE_URL, timeout=120000, wait_until="networkidle")
            page.wait_for_selector(
                "div.relative.bg-white.rounded-lg.shadow-sm", timeout=60000
            )
        except Exception as exc:
            html = page.content()
            with open(DEBUG_HTML, "w", encoding="utf-8") as fh:
                fh.write(html)
            browser.close()
            notify_slack(f"🛑 koppepanchi ページ読み込み失敗: {exc}")
            return []

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
                        if (parentLink) {
                            url = parentLink.href;
                        }
                    }

                    if (!url) {
                        const button = card.querySelector('button[data-url], button[data-href]');
                        if (button) {
                            url = button.getAttribute('data-url') || button.getAttribute('data-href') || '';
                        }
                    }

                    if (!url) {
                        const datasetUrl = card.getAttribute('data-url') || card.getAttribute('data-href');
                        if (datasetUrl) {
                            url = datasetUrl;
                        }
                    }

                    let pt = '';
                    const ptBlocks = card.querySelectorAll('span.px-1.vc_module__point-raw');
                    if (ptBlocks.length) {
                        pt = Array.from(ptBlocks)[ptBlocks.length - 1].textContent.replace(/\s+/g, '');
                    }

                    return { title, image, url, pt };
                }).filter(item => item.image || item.url || item.title);
            }
            """
        )

        html = page.content()
        browser.close()
        with open(DEBUG_HTML, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"📦 {len(items)} 件のカードを取得")
        return items


def main() -> None:
    sheet = get_sheet()
    existing_rows = sheet.get_all_values()[1:]
    existing_urls = {
        strip_query(row[2])
        for row in existing_rows
        if len(row) >= 3 and row[2].strip()
    }
    print(f"✅ 既存URL数: {len(existing_urls)}")

    items = fetch_items()
    if not items:
        print("📭 新規データなし")
        return

    new_rows: List[List[str]] = []
    for item in items:
        detail_url = (item.get("url") or "").strip()
        image_url = (item.get("image") or "").strip()
        title = (item.get("title") or "").strip() or "noname"
        pt_text = normalise_pt(item.get("pt") or "")

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        if not detail_url:
            print(f"⚠️ URL なしのためスキップ: {title}")
            continue

        norm_url = strip_query(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ 重複スキップ: {title} ({detail_url})")
            continue

        print(f"✅ 取得: {title} ({detail_url})")
        new_rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(norm_url)

    if not new_rows:
        print("📭 新規データなし")
        return

    try:
        sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"📥 {len(new_rows)} 件を追記")
    except Exception as exc:
        notify_slack(f"❌ スプレッドシート書き込み失敗: {exc}")
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - top level guard for logs
        notify_slack(f"❌ koppepanchi_scraper エラー: {exc}")
        raise
