import json
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def fetch_with_requests():
    url = "https://oripaone.jp"
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
        browser = p.chromium.launch(headless=True)
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
        page.goto("https://oripaone.jp", timeout=60000)
        try:
            page.wait_for_selector("div.overflow-hidden div.flex", timeout=60000)
        except Exception:
            # Scroll and wait again if first wait times out
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_selector("div.overflow-hidden div.flex", timeout=60000)
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


def scrape():
    # Try using requests first
    urls = fetch_with_requests()
    if not urls:
        urls = fetch_with_playwright()
    with open("banners.json", "w", encoding="utf-8") as f:
        json.dump(urls or [], f, ensure_ascii=False, indent=2)
    print(f"\u2705 {len(urls or [])} banner URLs retrieved")
