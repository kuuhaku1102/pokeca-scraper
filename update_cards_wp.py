import requests
import json
from slugify import slugify

# WordPress REST API 認証情報
WP_BASE = 'https://oripa-gacha.online/wp-json/wp/v2'
USERNAME = os.environ.get("WP_USER")
APP_PASSWORD = os.environ.get("WP_APP_PASS")

# GAS JSON URL（シート2）
GAS_URL = "https://script.google.com/macros/s/AKfycbxKsTu0RUAjNcxF3KFCgXX66ApxVouytSHisrrNHgJ-YN6QKyfTSYsAc4f9ismH2lB0Ww/exec"


# GAS からデータを取得
res = requests.get(GAS_URL)
data = res.json()

for row in data:
    title = row.get("カード名", "")
    slug = slugify(title)

    raw_json = row.get("直近価格JSON", "")
    if raw_json:
        prices = json.loads(raw_json)
    else:
        prices = {"美品": "-", "キズあり": "-", "PSA10": "-"}

    img = row.get("画像URL", row.get("画像", ""))
    beauty = prices.get("美品", "-")
    damaged = prices.get("キズあり", "-")
    psa10 = prices.get("PSA10", "-")

    # 1. 既存ポストをチェック
    check_url = f"{WP_BASE}/card?slug={slug}"
    check = requests.get(check_url, auth=(USERNAME, APP_PASSWORD))

    # 2. content部分（format形式に変更）
    content = """
        <p><img src='{img}'></p>
        <p>価格情報</p>
        <ul>
            <li>美品: {beauty}</li>
            <li>キズあり: {damaged}</li>
            <li>PSA10: {psa10}</li>
        </ul>
    """.format(img=img, beauty=beauty, damaged=damaged, psa10=psa10)

    post_data = {
        'title': title,
        'slug': slug,
        'status': 'publish',
        'content': content,
        'fields': {
            'card_image_url': img,
            'card_name': title,
            'model_number': row.get("型番", ""),
            'buy_price': row.get("買取価格", ""),
            'sell_price': row.get("販売価格", ""),
            'card_link': row.get("カード詳細URL", ""),
            'price_beauty': beauty,
            'price_damaged': damaged,
            'price_psa10': psa10
        }
    }

    if check.status_code == 200 and check.json():
        post_id = check.json()[0]['id']
        update_url = f"{WP_BASE}/card/{post_id}"
        r = requests.post(update_url, auth=(USERNAME, APP_PASSWORD), json=post_data)
        print(f"✅ Updated: {title}")
    else:
        r = requests.post(f"{WP_BASE}/card", auth=(USERNAME, APP_PASSWORD), json=post_data)
        print(f"🆕 Created: {title}")
