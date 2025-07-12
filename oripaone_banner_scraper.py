# oripaone_banner_scraper.py
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class OripaOneBannerScraper:
    def __init__(self):
        self.base_url = "https://oripaone.jp/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    async def scrape_with_playwright(self) -> Dict:
        """Playwrightを使用してバナー情報を取得"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.headers['User-Agent'],
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            try:
                # ページにアクセス
                await page.goto(self.base_url, wait_until='networkidle', timeout=30000)
                
                # Cloudflareのチェックを待機
                await page.wait_for_timeout(5000)
                
                # バナー画像を取得
                banners = await page.evaluate('''
                    () => {
                        const banners = [];
                        
                        // メインバナー（大きな画像）
                        const mainBanners = document.querySelectorAll('img[class*="aspect-"]');
                        mainBanners.forEach(img => {
                            if (img.src && img.src.includes('banners')) {
                                banners.push({
                                    type: 'main_banner',
                                    url: img.src,
                                    alt: img.alt || '',
                                    className: img.className,
                                    width: img.naturalWidth,
                                    height: img.naturalHeight
                                });
                            }
                        });
                        
                        // その他のプロモーション画像
                        const allImages = document.querySelectorAll('img');
                        allImages.forEach(img => {
                            if (img.src && (
                                img.src.includes('alert.png') ||
                                img.src.includes('coin.png') ||
                                img.src.includes('bingo') ||
                                img.src.includes('banners')
                            )) {
                                banners.push({
                                    type: 'promo_image',
                                    url: img.src,
                                    alt: img.alt || '',
                                    className: img.className,
                                    width: img.naturalWidth,
                                    height: img.naturalHeight
                                });
                            }
                        });
                        
                        return banners;
                    }
                ''')
                
                # 重複を削除
                unique_banners = []
                seen_urls = set()
                for banner in banners:
                    if banner['url'] not in seen_urls:
                        unique_banners.append(banner)
                        seen_urls.add(banner['url'])
                
                # ページタイトルとURL情報を追加
                page_info = {
                    'title': await page.title(),
                    'url': page.url,
                    'timestamp': datetime.now().isoformat(),
                    'banners': unique_banners
                }
                
                return page_info
                
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                return {'error': str(e), 'banners': []}
                
            finally:
                await browser.close()
    
    def download_banner(self, banner_url: str, filename: str) -> bool:
        """バナー画像をダウンロード"""
        try:
            response = self.session.get(banner_url, timeout=10)
            response.raise_for_status()
            
            # 保存ディレクトリを作成
            os.makedirs('banners', exist_ok=True)
            
            # ファイルを保存
            with open(f'banners/{filename}', 'wb') as f:
                f.write(response.content)
            
            print(f"バナーをダウンロードしました: {filename}")
            return True
            
        except Exception as e:
            print(f"バナーのダウンロードに失敗しました: {e}")
            return False
    
    def save_banner_data(self, data: Dict, filename: str = 'banner_data.json'):
        """バナー情報をJSONファイルに保存"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"バナー情報を保存しました: {filename}")
    
    async def run(self):
        """スクレイピングを実行"""
        print("オリパワンのバナーをスクレイピング中...")
        
        # バナー情報を取得
        banner_data = await self.scrape_with_playwright()
        
        if 'error' in banner_data:
            print(f"スクレイピングエラー: {banner_data['error']}")
            return
        
        # バナー情報を保存
        self.save_banner_data(banner_data)
        
        # バナー画像をダウンロード
        for i, banner in enumerate(banner_data.get('banners', [])):
            if banner['type'] == 'main_banner':
                # メインバナーのみダウンロード
                filename = f"main_banner_{i}.png"
                self.download_banner(banner['url'], filename)
        
        print("スクレイピング完了!")
        return banner_data


async def main():
    scraper = OripaOneBannerScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
