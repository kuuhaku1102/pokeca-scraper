# Pokeca Scraper

This repository contains Playwright scrapers for various card shop sites. The `ciel_scraper.py` script collects gacha information from [ciel-toreca.com](https://ciel-toreca.com/) and appends new entries to the `その他` sheet of the Google Spreadsheet.

- **title** – gacha title when available
- **image URL** – link to the thumbnail
- **URL** – link to the gacha detail page
- **PT** – point cost text

The scraper runs automatically via GitHub Actions.

This repository contains several scrapers for various card shop sites. A GitHub
Actions workflow automatically runs the Ciel scraper on a schedule.
main

[![.github/workflows/scrape_ciel.yml](https://github.com/kuuhaku1102/pokeca-scraper/actions/workflows/scrape_ciel.yml/badge.svg)](https://github.com/kuuhaku1102/pokeca-scraper/actions/workflows/scrape_ciel.yml)

## Iris Toreca Scraper

The `iris_scraper.py` script collects pack information from [iris-toreca.com](https://iris-toreca.com/). It uses `requests` and `BeautifulSoup` to scrape the list page and writes the result to the `その他` sheet in the same spreadsheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python iris_scraper.py
```

The workflow `.github/workflows/scrape_iris.yml` runs this scraper automatically on a schedule.
