import os
import base64
import re
from urllib.parse import urljoin, urlparse

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
import requests

BASE_URL = "https://dokkan-toreca.com/"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit"
SHEET_NAME = "その他"


def notify_slack(message: str) -> None:
    """Send error message to Slack if webhook is configured."""
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print(message)
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as exc:
        print(f"Slack notification failed: {exc}")
        print(message)


def save_credentials() -> str:
    """Write service account credentials from the environment."""
    encoded = os.environ.get("GSHEET_JSON", "")
    if not encoded:
        raise RuntimeError("GSHEET_JSON environment variable is missing")
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(encoded).decode("utf-8"))
    return "credentials.json"


def get_sheet():
    """Return gspread worksheet object."""
    creds_path = save_credentials()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def strip_query(url: str) -> str:
    """Remove query string from URL for deduplication."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def fetch_items() -> list:
    """Scrape gacha information from dokkan-toreca using Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 Loading dokkan-toreca…")
        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_selector("li.chakra-wrap__listitem", timeout=60000)
        except Exception as e:
            html = page.content()
            with open("dokkan_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            browser.close()
            notify_slack(f"🛑 Page load failed: {e}")
            return []

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
                    if (ptBox) pt = ptBox.textContent.replace(/\s+/g, '');
                    results.push({title, image: imgSrc, url: detail, pt});
                });
                return results;
            }
            """
        )
        browser.close()
        return items


def main() -> None:
    sheet = get_sheet()
    existing_data = sheet.get_all_values()[1:]
    existing_urls = {strip_query(row[2]) for row in existing_data if len(row) >= 3}
    print(f"✅ Existing {len(existing_urls)} URLs")

    items = fetch_items()
    if not items:
        print("📭 No data scraped")
        return

    new_rows = []
    for item in items:
        detail_url = item.get("url", "")
        image_url = item.get("image", "")
        title = item.get("title", "").strip() or "noname"
        pt_text = re.sub(r"[^0-9,]", "", item.get("pt", ""))

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        norm_url = strip_query(detail_url)
        if norm_url in existing_urls:
            print(f"⏭ Skip duplicate: {title}")
            continue

        print(f"✅ Fetched: {title}")
        new_rows.append([title, image_url, detail_url, pt_text])
        existing_urls.add(norm_url)

    if new_rows:
        try:
            sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
            print(f"📥 Appended {len(new_rows)} rows")
        except Exception as e:
            notify_slack(f"❌ Failed to write sheet: {e}")
    else:
        print("📭 No new data")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        notify_slack(f"❌ Script error: {exc}")
        raise
