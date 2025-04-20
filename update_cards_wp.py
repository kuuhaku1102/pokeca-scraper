import requests
import json
from slugify import slugify
import os

# WordPress REST API 認証情報
WP_BASE = 'https://oripa-gacha.online/wp-json/wp/v2'
USERNAME = os.environ.get("WP_USER")
APP_PASSWORD = os.environ.get("WP_APP_PASS")
GAS_URL = os.environ.get("GAS_URL")

headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

print("🚀 スクリプト起動しました！")
print(f"🧪 USERNAME: {USERNAME}")
print(f"🧪 GAS_URL: {GAS_URL}")

res = requests.get(GAS_URL)
print(f"🌐 GASレスポンスステータス: {res.status_code}")
print(f"🧾 レスポンス冒頭: {res.text[:100]}")

data = res.json()
print(f"📄 データ件数: {len(data)} 件")

for row in data:
    title = row.get("カード名", "").strip()
    if not title:
        print("⚠️ カード名が空のデータをスキップしました。")
        continue

    slug = slugify(title)
    print(f"⏳ 投稿チェック中: {title} ({slug})")

    raw_json = row.get("直近価格JSON", "")
    if raw_json:
        prices = json.loads(raw_json)
    else:
        prices = {"美品": "-", "キズあり": "-", "PSA10": "-"}

    img = row.get("画像URL", row.get("画像", ""))
    beauty = prices.get("美品", "-")
    damaged = prices.get("キズあり", "-")
    psa10 = prices.get("PSA10", "-")

    # 投稿本文
    content = f"""
        <p><img src="{img}" style="max-width:100%; height:auto;"></p>
        <p>価格情報</p>
        <ul>
            <li>美品: {beauty}</li>
            <li>キズあり: {damaged}</li>
            <li>PSA10: {psa10}</li>
        </ul>
    """

    # WordPress用のカスタムフィールド（meta）として保存
    meta = {
        "card_image_url": img,
        "card_name": title,
        "price_beauty": beauty.replace(",", "").replace("円", ""),
        "price_damaged": damaged.replace(",", "").replace("円", ""),
        "price_psa10": psa10.replace(",", "").replace("円", ""),
        "直近価格JSON": json.dumps(prices)
    }

    post_data = {
        "title": title,
        "slug": slug,
        "status": "publish",
        "content": content,
        "meta": meta
    }

    # 既存投稿をチェック → 更新 or 新規作成
    check_url = f"{WP_BASE}/card?slug={slug}"
    check = requests.get(check_url, auth=(USERNAME, APP_PASSWORD), headers=headers)

    if check.status_code == 200 and check.json():
        post_id = check.json()[0]["id"]
        update_url = f"{WP_BASE}/card/{post_id}"
        r = requests.post(update_url, auth=(USERNAME, APP_PASSWORD), json=post_data, headers=headers)
        print(f"✅ Updated: {title}")
    else:
        r = requests.post(f"{WP_BASE}/card", auth=(USERNAME, APP_PASSWORD), json=post_data, headers=headers)
        print(f"🆕 Created: {title}")
        print(f"📩 投稿レスポンス: {r.status_code}")
        print(f"📦 内容: {r.text[:200]}")

print("✅ 全投稿処理が完了しました。")
