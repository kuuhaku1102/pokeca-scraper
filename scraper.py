# driver.quit() の下に追加！

import pymysql
import json

# DB接続
conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    database=os.environ["DB_NAME"],
    charset='utf8mb4'
)
cursor = conn.cursor()

for i, url in enumerate(urls, start=2):
    if not url.startswith("http"):
        continue
    card_title = ws.cell(i, 1).value
    data_row = ws.row_values(i)[3:]  # D列以降

    sql = """
    INSERT INTO wp_pokeca_prices (
      card_title, image_url, card_url,
      price_b, price_k, price_p
    ) VALUES (%s, %s, %s, %s, %s, %s)
    """

    b = data_row[0:7]
    k = data_row[7:14]
    p = data_row[14:21]

    cursor.execute(sql, (
        card_title,
        "",  # ←画像がない場合は空欄に（必要なら埋めてもOK）
        url,
        json.dumps(dict(zip(labels, b)), ensure_ascii=False),
        json.dumps(dict(zip(labels, k)), ensure_ascii=False),
        json.dumps(dict(zip(labels, p)), ensure_ascii=False),
    ))

conn.commit()
cursor.close()
conn.close()

print("✅ Googleシート & MySQL 両方に保存完了！")
