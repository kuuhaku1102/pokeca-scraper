name: Scrape OripaOne Banners

on:
  schedule:
    - cron: '0 0 * * *'  # 毎日 JST 9:00（UTC 0:00）
  workflow_dispatch:
  push:
    branches: [ main ]

permissions:
  contents: write
  issues: write

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Cache pip dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          playwright install chromium

      - name: Run OripaOne banner scraper
        run: python oripaone_banner_scraper.py

      - name: Upload banner data and images as artifact
        uses: actions/upload-artifact@v4
        with:
          name: oripaone-banner-${{ github.run_number }}
          path: |
            banner_data.json
            banners/
          retention-days: 30

      - name: Commit & push if data changed
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add banner_data.json banners/
          if git diff --cached --quiet; then
            echo "No changes to commit."
          else
            git commit -m "Update banner data: $(date -u)"
            git push
          fi
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Create issue if scraping failed
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🚨 OripaOneバナースクレイピング失敗',
              body: 'バナーのスクレイピング処理が失敗しました。\nログを確認してください。',
              labels: ['bug', 'scraping']
            })
