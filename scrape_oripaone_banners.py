import json
from playwright.sync_api import sync_playwright

def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://oripaone.jp", timeout=30000)
        page.wait_for_selector("div.overflow-hidden div.flex")

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

        with open("banners.json", "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)

        print(f"✅ {len(urls)} 件のバナー画像URLを取得しました")
        browser.close()

if __name__ == "__main__":
    scrape()
