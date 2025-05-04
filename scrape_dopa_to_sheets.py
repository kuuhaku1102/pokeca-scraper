import os
import requests
from bs4 import BeautifulSoup

# 環境変数からGASのURLを取得
GAS_URL = os.getenv("GAS_URL")
BASE_URL = "https://dopa-game.jp"

def scrape_dopa():
    res = requests.get(BASE_URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    gacha_items = soup.select("div[class*=col-] > a[href*='itemDetail']")
    results = []

    for a in gacha_items:
        img_tag = a.select_one("img")
        if img_tag:
            img_url = img_tag["src"]
            title = img_tag.get("alt", "").strip()  # alt属性にタイトルがあれば
            link = a["href"]

            results.append({
                "タイトル": title or "無題",
                "画像URL": BASE_URL + img_url if img_url.startswith("/") else img_url,
                "URL": BASE_URL + link if link.startswith("/") else link
            })

    return results

def post_to_gas(data):
    if not GAS_URL:
        print("GAS_URL not defined")
        return
    res = requests.post(GAS_URL, json={"records": data})
    print(res.status_code, res.text)

if __name__ == "__main__":
    gacha_list = scrape_dopa()
    if gacha_list:
        post_to_gas(gacha_list)
