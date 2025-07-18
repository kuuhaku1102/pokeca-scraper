#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oripaone.jp のトップページからバナー画像を取得するスクリプト。
取得した画像 URL を banners.json に保存します。
"""

import json
import requests
from bs4 import BeautifulSoup

def main():
    url = 'https://oripaone.jp'
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; BannerScraper/1.0)'
    }
    # ページの HTML を取得
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')

    # お知らせバナーのコンテナを特定
    container = soup.select_one('div.overflow-hidden div.flex')
    if not container:
        raise RuntimeError("お知らせバナーのコンテナが見つかりませんでした")

    img_tags = container.find_all('img')
    banner_urls = []

    for img in img_tags:
        # srcset があれば一番大きいサイズを選択
        srcset = img.get('srcset')
        if srcset:
            # 640w 750w のように複数指定されているので最後のURLを取得
            sources = [s.strip().split(' ')[0] for s in srcset.split(',')]
            banner_urls.append(sources[-1])
        else:
            banner_urls.append(img.get('src'))

    # JSONファイルとして出力
    with open('banners.json', 'w', encoding='utf-8') as f:
        json.dump(banner_urls, f, ensure_ascii=False, indent=2)

    print(f'Collected {len(banner_urls)} banner images:')
    for url in banner_urls:
        print(url)

if __name__ == '__main__':
    main()
