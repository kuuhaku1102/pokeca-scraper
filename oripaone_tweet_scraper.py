from playwright.sync_api import sync_playwright
import time

SEARCH_URL = "https://twitter.com/search?q=オリパワン%20当たり&src=typed_query&f=live"

def scrape_tweets():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile Safari/604.1")
        page = context.new_page()
        page.goto(SEARCH_URL, timeout=60000)

        time.sleep(5)  # 表示待ち（必要ならスクロールしてもOK）

        tweets = page.locator("article").all()
        for i, tweet in enumerate(tweets[:5]):  # 上位5件だけ
            print(f"--- Tweet {i+1} ---")
            print(tweet.inner_text())
            print("")

        browser.close()

if __name__ == "__main__":
    scrape_tweets()
