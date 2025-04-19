import requests
import json
from slugify import slugify

# WordPress REST API 認証情報
WP_BASE = 'https://oripa-gacha.online/wp-json/wp/v2'
USERNAME = 'blank'
APP_PASSWORD = 'LWBX hVGw h23K r1ik sQMv 5pVO'

# GAS JSON URL（シート2）
GAS_URL = 'https://script.google.com/macros/s/AKfycb.../exec?sheet=シート2'

# GAS からデータを取得
res = requests.get(GAS_URL)
data = res.json()

for row in data:
    title = row.get("\u30ab\u30fc\u30c9\u540d", "")
    slug = slugify(title)

    # 1. 既存ポストをチェック
    check_url = f"{WP_BASE}/card?slug={slug}"
    check = requests.get(check_url, auth=(USERNAME, APP_PASSWORD))

    # 2. 資料の構築
    content = f"""
        <p><img src='{row.get("\u753b\u50cfURL", row.get("\u753b\u50cf", ""))}'></p>
        <p>価格情報</p>
        <ul>
            <li>美品: {json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("\u7f8e\u54c1", '-')}</li>
            <li>キズあり: {json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("\u30ad\u30ba\u3042\u308a", '-')}</li>
            <li>PSA10: {json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("PSA10", '-')}</li>
        </ul>
    """

    post_data = {
        'title': title,
        'slug': slug,
        'status': 'publish',
        'content': content,
        'fields': {
            'card_image_url': row.get("\u753b\u50cfURL", ""),
            'card_name': row.get("\u30ab\u30fc\u30c9\u540d", ""),
            'model_number': row.get("\u578b\u756a", ""),
            'buy_price': row.get("\u8cb0\u53d6\u4fa1\u683c", ""),
            'sell_price': row.get("\u8ca9\u58f2\u4fa1\u683c", ""),
            'card_link': row.get("\u30ab\u30fc\u30c9\u8a73\u7d30URL", ""),
            'price_beauty': json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("\u7f8e\u54c1", ""),
            'price_damaged': json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("\u30ad\u30ba\u3042\u308a", ""),
            'price_psa10': json.loads(row.get("\u76f4\u8fd1\u4fa1\u683cJSON", '{}')).get("PSA10", "")
        }
    }

    # 3. 既存していれば PUT, 新規なら POST
    if check.status_code == 200 and check.json():
        post_id = check.json()[0]['id']
        update_url = f"{WP_BASE}/card/{post_id}"
        r = requests.post(update_url, auth=(USERNAME, APP_PASSWORD), json=post_data)
        print(f"✅ Updated: {title}")
    else:
        r = requests.post(f"{WP_BASE}/card", auth=(USERNAME, APP_PASSWORD), json=post_data)
        print(f"🆕 Created: {title}")
