import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin

import requests
import gspread
import base64
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright


class OripaOneBannerScraper:
    def __init__(self):
        self.base_url = "https://oripaone.jp/"
        self.sheet_name = "news"
        self.sheet_url = os.environ.get("SPREADSHEET_URL")
        self.gsheet_json = os.environ.get("GSHEET_JSON")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })

    def save_banner_data(self, data: Dict, filename: str = 'banner_data.json'):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON保存完了: {filename}")

    def download_banner(self, banner_url: str, filename: str) -> bool:
        try:
            response = self.session.get(banner_url, timeout=10)
            response.raise_for_status()
            os.makedirs('banners', exist_ok=True)
            with open(f'banners/{filename}', 'wb') as f:
                f.write(response.content)
            print(f"📥 バナー保存: {filename}")
            return True
        except Exception as e:
            print(f"❌ バナー保存失敗: {e}")
            return False

    async def scrape_with_playwright(self) -> Dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                print("🌐 ページにアクセス中...")
                await page.goto(self.base_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(5000)

                banners = await page.evaluate('''() => {
                    const results = [];
                    const imgs = document.querySelectorAll("img");
                    imgs.forEach(img => {
                        if (img.src && img.src.match(/banner|banners|top|pickup|main/i)) {
                            const link = img.closest("a");
                            results.push({
                                src: img.src,
                                href: link ? link.href : "",
                                alt: img.alt || ""
                            });
                        }
                    });
                    return results;
                }''')

                return {
                    "title": await page.title(),
                    "url": page.url,
                    "timestamp": datetime.now().isoformat(),
                    "banners": banners,
                }

            except Exception as e:
                return {"error": str(e), "banners": []}
            finally:
                await browser.close()

    def write_to_google_sheet(self, banners: List[Dict]):
        if not self.gsheet_json or not self.sheet_url:
            raise RuntimeError("❌ GSHEET_JSON または SPREADSHEET_URL が未設定です")

        creds_path = "credentials.json"
        with open(creds_path, "w") as f:
            f.write(base64.b64decode(self.gsheet_json).decode("utf-8"))

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(self.sheet_url).worksheet(self.sheet_name)

        existing = set(row[0] for row in sheet.get_all_values()[1:] if row)
        new_rows = []

        for b in banners:
            full_url = urljoin(self.base_url, b["src"])
            if full_url not in existing:
                new_rows.append([full_url, b.get("href", self.base_url)])

        if new_rows:
            sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
            print(f"📝 スプレッドシートに {len(new_rows)} 件追加しました")
        else:
            print("📭 追加対象なし（重複）")

    async def run(self):
        print("🚀 スクレイピング開始")
        result = await self.scrape_with_playwright()

        if "error" in result:
            print("❌ エラー:", result["error"])
            return

        print(f"🖼️ バナー数: {len(result['banners'])}")
        if result["banners"]:
            print(f"🔍 最初のバナー: {result['banners'][0]}")

        self.save_banner_data(result)

        for i, banner in enumerate(result["banners"]):
            full_url = urljoin(self.base_url, banner["src"])
            self.download_banner(full_url, f"banner_{i}.png")

        try:
            self.write_to_google_sheet(result["banners"])
        except Exception as e:
            print(f"❌ スプレッドシート書き込み失敗: {e}")

        print("🎉 完了！")


async def main():
    scraper = OripaOneBannerScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
