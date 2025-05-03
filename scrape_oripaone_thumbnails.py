import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# セットアップ
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ページを開く
url = "https://oripaone.jp/"
driver.get(url)
time.sleep(3)

# HTMLを解析
soup = BeautifulSoup(driver.page_source, "html.parser")
driver.quit()

# サムネイル抽出
thumbnails = []
for img in soup.find_all("img"):
    src = img.get("src", "")
    if "packs" in src:
        if src.startswith("http"):
            thumbnails.append(src)
        else:
            thumbnails.append("https://oripaone.jp" + src)

# 結果出力
for thumb in thumbnails[:20]:
    print(thumb)
