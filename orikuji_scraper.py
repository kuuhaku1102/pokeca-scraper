def scrape_orikuji(existing_paths: set) -> List[List[str]]:
    rows: List[List[str]] = []
    with sync_playwright() as p:
        # headless=False なら画面で確認できる
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        print("🔍 orikuji.com スクレイピング開始...")

        try:
            page.goto(BASE_URL, timeout=60000, wait_until="networkidle")

            # 強化版: すべてのwhite-boxを順番にscrollIntoView
            def scroll_to_load_all(page, selector="div.white-box", max_tries=30):
                prev_count = 0
                for i in range(max_tries):
                    boxes = page.query_selector_all(selector)
                    for box in boxes:
                        try:
                            box.scroll_into_view_if_needed()
                            page.wait_for_timeout(150)
                        except Exception:
                            pass
                    curr_count = len(page.query_selector_all(selector))
                    if curr_count == prev_count:
                        break
                    prev_count = curr_count
                print(f"👀 {curr_count}件の {selector} を検出")
            scroll_to_load_all(page)

            page.wait_for_selector("div.white-box img", timeout=60000)

            items = page.evaluate(
                """
                () => {
                    const results = [];
                    document.querySelectorAll('div.white-box').forEach(box => {
                        const link = box.querySelector('a[href*="/gacha/"]');
                        const img = box.querySelector('div.image-container img');
                        if (!link || !img) return;
                        const imgSrc = img.getAttribute('data-src') || img.getAttribute('src') || '';
                        if (
                            imgSrc.includes('/img/coin.png') ||
                            imgSrc.includes('/coin/lb_coin_')
                        ) return;

                        const title = img.getAttribute('alt') || 'noname';
                        const image = imgSrc;
                        const url = link.getAttribute('href') || '';
                        const ptEl = box.querySelector('span.coin-area');
                        const pt = ptEl ? ptEl.textContent.trim() : '';
                        results.push({ title, image, url, pt });
                    });
                    return results;
                }
                """
            )
            print(f"取得したitems件数: {len(items)}")
            for item in items:
                print(f"item url: {item.get('url', '')}")
        except Exception as exc:
            print(f"🛑 ページ読み込み失敗: {exc}")
            browser.close()
            return rows
        browser.close()

    for item in items:
        detail_url = item.get("url", "").strip()
        image_url = item.get("image", "").strip()
        title = item.get("title", "noname").strip() or "noname"
        pt_text = item.get("pt", "").strip()

        if detail_url.startswith("/"):
            detail_url = urljoin(BASE_URL, detail_url)
        if image_url.startswith("/"):
            image_url = urljoin(BASE_URL, image_url)

        path = urlparse(detail_url).path
        print(f"追加判定: {title} | path: {path} | 重複: {path in existing_paths}")
        if path in existing_paths:
            print(f"⏭ スキップ（重複）: {title}")
            continue

        rows.append([title, image_url, detail_url, pt_text])
        existing_paths.add(path)

    return rows
