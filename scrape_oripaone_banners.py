import os
import base64
import json
import time
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://oripaone.jp"
TARGET_URL = BASE_URL
SHEET_NAME = "news"
SPREADSHEET_URL = os.environ.get("SPREADSHEET_URL")


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
    if not SPREADSHEET_URL:
        raise RuntimeError("SPREADSHEET_URL environment variable is missing")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(SHEET_NAME)


def fetch_existing_image_urls(sheet) -> set:
    records = sheet.get_all_values()
    urls = set()
    for row in records[1:]:
        if len(row) >= 1:
            urls.add(row[0].strip())
    return urls


def fetch_with_requests():
    url = TARGET_URL
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    container = soup.select_one("div.overflow-hidden div.flex")
    if not container:
        return None
    urls = []
    for img in container.find_all("img"):
        srcset = img.get("srcset")
        if srcset:
            candidates = [s.strip().split(" ")[0] for s in srcset.split(",")] 
            urls.append(candidates[-1])
        else:
            src = img.get("src")
            if src:
                urls.append(src)
    return urls


def fetch_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Referer": "https://www.google.com/",
            },
        )
        page = context.new_page()
        page.goto(TARGET_URL, timeout=60000)
        try:
            page.wait_for_selector("div.overflow-hidden div.flex", timeout=60000)
        except Exception:
            
            page.wait_for_selector("div.overflow-hidden div.flex", timeout=60000)
            

def fetch_with_playwright_new() -> list[str]:
    """Fetch banner images using Playwright, capturing all slides."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Referer": "https://www.google.com/",
            },
        )
        page = context.new_page()
        page.goto(TARGET_URL, timeout=60000)
        try:
            page.wait_for_selector("div[aria-roledescription='slide'] img", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception:
                            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_selector("div[aria-roledescription='slide'] img", timeout=60000)
            page.wait_for_timeout(3000)
                img_elements = page.query_selector_all("div[aria-roledescription='slide'] img")
        urls: list[str] = []
        for img in img_elements:
            srcset = img.get_attribute("srcset")
            if srcset:
                candidates = [s.strip().split(" ")[0] for s in srcset.split(",")]
                urls.append(candidates[-1])
            else:
                src = img.get_attribute("src")
                if src:
                    urls.append(src)
        context.close()
        browser.close()
        return urls

        img_elements = page.query_selector_all("div.overflow-hidden div.flex img")
        urls = []
        for img in img_elements:
            srcset = img.get_attribute("srcset")
            if srcset:
                candidates = [s.strip().split(" ")[0] for s in srcset.split(",")]
                urls.append(candidates[-1])
            else:
                src = img.get_attribute("src")
                if src:
                    urls.append(src)
        context.close()
        browser.close()
        return urls


def scrape_banners(existing_urls: set):
    urls = fetch_with_requests()
    if not urls:
        urls = fetch_with_playwright_new()
    rows = []
    if not urls:
        return rows
    for url in urls:
        # ensure full URL if relative
        if url.startswith("/"):
            full_url = urljoin(BASE_URL, url)
        else:
            full_url = url
        if full_url not in existing_urls:
            rows.append([full_url, TARGET_URL])
            existing_urls.add(full_url)
    return rows


def main() -> None:
    sheet = get_sheet()
    existing = fetch_existing_image_urls(sheet)
    rows = scrape_banners(existing)
    if not rows:
        print("📭 新規データなし")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"📥 {len(rows)} 件追記完了")


if __name__ == "__main__":
    main()
