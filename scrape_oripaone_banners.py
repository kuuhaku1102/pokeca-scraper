import json
import requests
from bs4 import BeautifulSoup

def main():
    url = 'https://oripaone.jp/'

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/115.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com',
        'DNT': '1',  # Do Not Track
        'Upgrade-Insecure-Requests': '1'
    }

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')

    container = soup.select_one('div.overflow-hidden div.flex')
    if not container:
        raise RuntimeError("お知らせバナーのコンテナが見つかりません")

    img_tags = container.find_all('img')
    banner_urls = []

    for img in img_tags:
        srcset = img.get('srcset')
        if srcset:
            sources = [s.strip().split(' ')[0] for s in srcset.split(',')]
            banner_urls.append(sources[-1])  # 最も大きい画像
        else:
            banner_urls.append(img.get('src'))

    with open('banners.json', 'w', encoding='utf-8') as f:
        json.dump(banner_urls, f, ensure_ascii=False, indent=2)

    print(f'✅ {len(banner_urls)}件のバナー画像を取得しました')
    for url in banner_urls:
        print(url)

if __name__ == '__main__':
    main()
