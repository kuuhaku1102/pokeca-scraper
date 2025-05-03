import requests
from bs4 import BeautifulSoup

def scrape_images():
    url = "https://oripa-dash.com/user/packList"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    # div[3] の中に複数の pack があると仮定
    for div in soup.select("div.userPagePackList__item"):  # セレクタは仮、正確に調整必要
        img_tag = div.select_one("img")
        if img_tag and "src" in img_tag.attrs:
            image_url = img_tag["src"]
            if image_url.startswith("/"):
                image_url = "https://oripa-dash.com" + image_url
            results.append(image_url)

    return results

if __name__ == "__main__":
    imgs = scrape_images()
    for i in imgs:
        print(i)
