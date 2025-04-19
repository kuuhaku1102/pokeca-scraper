import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/11agq4oxQxT1g9ZNw_Ad9g7nc7PvytHr1uH5BSpwomiE/edit")
ws = sheet.worksheet("シート1")

urls = ws.col_values(3)[1:]

sections = ["美品", "キズあり", "PSA10"]
labels = ["データ数", "直近価格", "最高価格", "平均価格", "最低価格", "騰落率(7日)", "騰落率(30日)"]
headers = [f"{s}_{l}" for s in sections for l in labels]
ws.update('D1', [headers])

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

for i, url in enumerate(urls, start=2):
    if not url.startswith("http"):
        continue
    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    table = soup.find("tbody", id="item-price-table")
    data = []
    if table:
        for row in table.find_all("tr"):
            tds = row.find_all("td")
            for td in tds[1:4]:
                val = td.get_text(strip=True).replace(",", "").replace("円", "").replace("%", "").replace("(", "").replace(")", "")
                data.append(val)
    else:
        data = [""] * len(headers)
    ws.update(f'D{i}', [data])

driver.quit()
