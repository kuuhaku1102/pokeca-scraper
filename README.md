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

## Oripa ex-toreca Scraper

The `oripa_ex_scraper.py` script scrapes pack data from [oripa.ex-toreca.com](https://oripa.ex-toreca.com/). It uses `requests` and `BeautifulSoup` to gather pack titles, image URLs, detail page links and PT values, then appends them to the `その他` sheet of the same spreadsheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python oripa_ex_scraper.py
```

This scraper is executed automatically via the `.github/workflows/scrape_oripa_ex.yml` workflow.

## Dokkan Toreca Scraper

The `dokkan_scraper.py` script collects gacha details from [dokkan-toreca.com](https://dokkan-toreca.com/). It uses Playwright to scrape the top page and appends new rows to the `その他` sheet with the title, banner image URL, detail page URL and PT value. Existing URLs are skipped to avoid duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python dokkan_scraper.py
```

The workflow `.github/workflows/scrape_dokkan.yml` runs this scraper weekly.
