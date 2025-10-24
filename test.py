import requests

# --- WordPress REST APIエンドポイント ---
WP_URL = "https://online-gacha-hack.com/wp-json/oripa/v1/upsert"

# --- Basic認証用（WPユーザー + アプリケーションパスワード） ---
WP_USER = "admin"
WP_APP_PASS = "SRWvWpV0B9aYVAlfl74vKweQ"  # ← スペースを全て削除

# --- テスト投稿データ ---
data = [{
    "source_slug": "oripa-dash",
    "title": "テストアイテム",
    "image_url": "https://example.com/image.jpg",
    "detail_url": "https://example.com/detail/test",
    "price": 1000,
    "points": 10,
    "rarity": "PSA10"
}]

# --- POST送信 ---
res = requests.post(WP_URL, json=data, auth=(WP_USER, WP_APP_PASS))
print("Status:", res.status_code)
print("Response:", res.text)
