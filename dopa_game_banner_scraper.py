from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://dopa-game.jp", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    time.sleep(5)
    imgs = page.query_selector_all("img.chakra-image")
    print(f"Found {len(imgs)} images")
    for img in imgs:
        print(img.get_attribute("src"))
    with open("debug.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    browser.close()
