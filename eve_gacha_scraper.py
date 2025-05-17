def fetch_items(existing_urls: set) -> List[List[str]]:
    """Scrape gacha info from eve-gacha.com using Playwright."""
    rows: List[List[str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=60000)
        page.wait_for_timeout(3000)

        cards = page.query_selector_all("a[href*='/gacha/']")
        print(f"取得したaタグ数: {len(cards)}")
        if len(cards) == 0:
            print("⚠️ Playwright経由でもaタグがゼロなら、セレクタ再調整やJS側の仕様変更を疑ってください")
        for a in cards:
            detail_url = a.get_attribute("href")
            if not detail_url:
                continue
            if detail_url.startswith("/"):
                detail_url = urljoin(BASE_URL, detail_url)
            detail_url = detail_url.strip()
            if detail_url in existing_urls:
                continue

            # カードのimg/タイトル/PT等を抽出
            img = a.query_selector("img")
            image_url = ""
            title = "noname"
            if img:
                image_url = img.get_attribute("data-src") or img.get_attribute("src") or ""
                if image_url.startswith("/"):
                    image_url = urljoin(BASE_URL, image_url)
                image_url = image_url.strip()
                alt = img.get_attribute("alt") or img.get_attribute("title")
                if alt:
                    title = alt.strip() or title
            if title == "noname":
                text = a.inner_text().strip()
                if text:
                    title = text.split()[0]

            # --- ここからPT取得ロジック ---
            pt = ""
            # 親divを遡って価格部分を探す
            parent_div = a
            for _ in range(4):  # 最大4階層遡る
                parent_div = parent_div.evaluate_handle("el => el.parentElement")
            # この親div内で「/1回」表記の直前の数値などを抽出
            pt_element = None
            if parent_div:
                # よく使われている価格表記を探索
                pt_element = parent_div.query_selector("span.font-bold")
                if not pt_element:
                    pt_element = parent_div.query_selector("div.flex.items-end.gap-1.5 span.text-white")
                if pt_element:
                    pt_text = pt_element.inner_text().strip()
                    m = re.search(r"(\d{3,6})", pt_text.replace(",", ""))
                    if m:
                        pt = m.group(1)
            # フォールバック（取れない場合は空欄）
            rows.append([title, image_url, detail_url, pt])
            existing_urls.add(detail_url)
        browser.close()
    return rows
