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


## Dokkan Banner Scraper

The `dokkan_banner_scraper.py` script retrieves banner image URLs from [dokkan-toreca.com](https://dokkan-toreca.com/). It uses Playwright to collect the image URL from the top page slider and appends it to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python dokkan_banner_scraper.py
```

The workflow `.github/workflows/scrape_dokkan_banner.yml` runs this scraper automatically.

## Spark Oripa Scraper

The `sparkoripa_scraper.py` script collects gacha data from [sparkoripa.jp](https://sparkoripa.jp/). It uses `requests` and `BeautifulSoup` to scrape the top page and appends the title, image URL, detail page URL and PT value to the `その他` sheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python sparkoripa_scraper.py
```

The workflow `.github/workflows/scrape_sparkoripa.yml` runs this scraper on a schedule.

## Eve Gacha Scraper

The `eve_gacha_scraper.py` script gathers gacha information from [eve-gacha.com](https://eve-gacha.com/). It uses `requests` and `BeautifulSoup` to scrape the top page and appends the title, image URL, detail page URL and PT value to the `その他` sheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python eve_gacha_scraper.py
```

The workflow `.github/workflows/scrape_evegacha.yml` runs this scraper automatically.

## Japan Toreca Scraper

The `japan_toreca_scraper.py` script collects oripa information from [japan-toreca.com](https://japan-toreca.com/). It uses Playwright to scrape the top page and appends the title, image URL, detail page URL and PT value to the `その他` sheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python japan_toreca_scraper.py
```

The workflow `.github/workflows/scrape_japan_toreca.yml` runs this scraper automatically.

## Orikuji Scraper

The `orikuji_scraper.py` script fetches gacha information from [orikuji.com](https://orikuji.com/). It uses Playwright to collect the title, image URL, detail page link and PT value from the front page, skipping entries that already exist in the `その他` sheet.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python orikuji_scraper.py
```

The workflow `.github/workflows/scrape_orikuji.yml` runs this scraper automatically.

## Dopa Game Scraper

The `dopa_game_scraper.py` script collects gacha information from [dopa-game.jp](https://dopa-game.jp/). It uses Playwright to fetch the list page and extracts the title, thumbnail URL, detail page link and PT value. New entries are appended to the `その他` sheet, skipping rows with a duplicate detail URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python dopa_game_scraper.py
```

The workflow `.github/workflows/scrape_dopa_game.yml` runs this scraper automatically.

## Dopa Game Banner Scraper

The `dopa_game_banner_scraper.py` script retrieves banner image URLs from [dopa-game.jp](https://dopa-game.jp/). It uses Playwright to collect the alt text, image URL and site URL from the top page slider and appends them to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python dopa_game_banner_scraper.py
```

The workflow `.github/workflows/scrape_dopa_banner.yml` runs this scraper automatically.


## Oripa Dash Banner Scraper


The `oripa_dash_banner_scraper.py` script retrieves banner image URLs from [oripa-dash.com](https://oripa-dash.com/user/packList). It uses Playwright to collect each banner's image URL and link URL from the top slider and appends them to the `news` sheet, skipping entries with a duplicate image URL.

The `oripa_dash_banner_scraper.py` script retrieves banner image URLs from [oripa-dash.com](https://oripa-dash.com/user/packList). It uses Playwright to collect the image URL and site URL from the top slider and appends them to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python oripa_dash_banner_scraper.py
```

The workflow `.github/workflows/scrape_oripa_dash_banner.yml` runs this scraper automatically.

## Oripa ex Banner Scraper

The `oripa_ex_banner_scraper.py` script retrieves banner image URLs from [oripa.ex-toreca.com](https://oripa.ex-toreca.com/). It uses Playwright to collect the image URL and link URL from the top slider and appends them to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python oripa_ex_banner_scraper.py
```

The workflow `.github/workflows/scrape_oripa_ex_banner.yml` runs this scraper automatically.

## Oripaone Banner Scraper

The `oripaone_banner_scraper.py` script retrieves banner image URLs from [oripaone.jp](https://oripaone.jp/). It uses Playwright to collect the image URL and link URL from the top slider and appends them to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python oripaone_banner_scraper.py
```

The workflow `.github/workflows/scrape_oripaone_banner.yml` runs this scraper automatically.

## Ram Oripa Scraper

The `ram_oripa_scraper.py` script gathers gacha information from [ram-oripa.com](https://ram-oripa.com/). It uses Playwright to scrape the top page and collects the title, image URL, detail page URL and PT value. New entries are appended to the `その他` sheet, skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python ram_oripa_scraper.py
```

The workflow `.github/workflows/scrape_ram_oripa.yml` runs this scraper automatically.


## Toreca Rainbow Oripa Scraper

The `oripa_toreca_rainbow_scraper.py` script collects gacha data from [oripa.toreca-rainbow.com](https://oripa.toreca-rainbow.com/). It uses Playwright to grab the title, image URL, detail page URL and PT value from the top page and appends new rows to the `その他` sheet. Existing URLs are skipped to avoid duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python oripa_toreca_rainbow_scraper.py
```

The workflow `.github/workflows/scrape_toreca_rainbow.yml` runs this scraper automatically.

## Ichica Scraper

The `ichica_scraper.py` script collects gacha information from [ichica.co](https://ichica.co/). It uses Playwright to gather the title, image URL, detail page URL and PT value from the main page. New rows are appended to the `その他` sheet, skipping entries with a duplicate URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python ichica_scraper.py
```

The workflow `.github/workflows/scrape_ichica.yml` runs this scraper automatically.

## Ichica Banner Scraper

The `ichica_banner_scraper.py` script retrieves banner image URLs from [ichica.co](https://ichica.co/). It uses Playwright to collect the image URL from the banner carousel (element `#testing`) and appends them to the `news` sheet, skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python ichica_banner_scraper.py
```

The workflow `.github/workflows/scrape_ichica_banner.yml` runs this scraper automatically.

## Ichica Recommended Banner Scraper

The `ichica_lotteries_banner_scraper.py` script retrieves banner images from the [recommended lotteries page](https://ichica.co/?tab=Lotteries&dds=recommended) on [ichica.co](https://ichica.co/). It uses Playwright to collect each image URL from the element `#testing` and appends them to the `news` sheet while skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python ichica_lotteries_banner_scraper.py
```

The workflow `.github/workflows/scrape_ichica_lotteries_banner.yml` runs this scraper automatically.

## Clove Oripa Pokemon Banner Scraper

The `clove_oripa_pokemon_banner_scraper.py` script retrieves banner images from [oripa.clove.jp/oripa/Pokemon](https://oripa.clove.jp/oripa/Pokemon). It uses Playwright to collect each banner image URL from the top slider and appends them to the `news` sheet while skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python clove_oripa_pokemon_banner_scraper.py
```

If scraping fails, the page HTML is saved to `clove_oripa_pokemon_banner_debug.html` for inspection.

The workflow `.github/workflows/scrape_clove_oripa_pokemon_banner.yml` runs this scraper automatically.

## Oripalette Scraper

The `oripalette_scraper.py` script collects gacha information from [oripalette.jp](https://oripalette.jp/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python oripalette_scraper.py
```

The workflow `.github/workflows/scrape_oripalette.yml` runs this scraper automatically.

## Smash High Scraper

The `smash_high_scraper.py` script collects gacha information from [smash-high.co.jp](https://smash-high.co.jp/). It uses Playwright to scrape the top page and gathers the item title (from the image's `alt` attribute), image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python smash_high_scraper.py
```

The workflow `.github/workflows/scrape_smash_high.yml` runs this scraper automatically.

## YK Oripa Scraper

The `yk_oripa_scraper.py` script collects gacha information from [yk-oripa.com](https://yk-oripa.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python yk_oripa_scraper.py
```

The workflow `.github/workflows/scrape_yk_oripa.yml` runs this scraper automatically.

## Toreca.io Scraper

The `toreca_io_scraper.py` script collects gacha information from [toreca.io](https://toreca.io/). It uses Playwright to scrape the main page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python toreca_io_scraper.py
```

The workflow `.github/workflows/scrape_toreca_io.yml` runs this scraper automatically.

## Dokodemo Oripa Scraper

The `dokodemooripa_scraper.py` script collects gacha information from [dokodemooripa.com](https://dokodemooripa.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python dokodemooripa_scraper.py
```

The workflow `.github/workflows/scrape_dokodemooripa.yml` runs this scraper automatically.

## Alpha Oripa Scraper

The `alpha_oripa_scraper.py` script collects gacha information from [alpha-oripa.com](https://alpha-oripa.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python alpha_oripa_scraper.py
```

The workflow `.github/workflows/scrape_alpha_oripa.yml` runs this scraper automatically.

## Black Gacha Scraper

The `blackgacha_scraper.py` script gathers gacha information from [blackgacha.com](https://blackgacha.com/). It uses Playwright to scrape the top page and collects the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python blackgacha_scraper.py
```

The workflow `.github/workflows/scrape_blackgacha.yml` runs this scraper automatically.

## Torekazi Scraper

The `torekazi_scraper.py` script collects gacha information from [torekazi.com](https://torekazi.com/). It uses Playwright to scrape the main page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python torekazi_scraper.py
```

The workflow `.github/workflows/scrape_torekazi.yml` runs this scraper automatically.

## Sweet Toreka Scraper

The `sweet_toreka_scraper.py` script collects gacha information from [sweet-toreka.com](https://sweet-toreka.com/). It uses Playwright to scrape the main page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python sweet_toreka_scraper.py
```

The workflow `.github/workflows/scrape_sweet_toreka.yml` runs this scraper automatically.

## Jin Studio Oripa Scraper

The `jinstudiooripa_scraper.py` script collects gacha information from [jinstudiooripa.com](https://jinstudiooripa.com/product/pokemon). It uses Playwright to scrape the listing page and extracts the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
python jinstudiooripa_scraper.py
```

The workflow `.github/workflows/scrape_jinstudiooripa.yml` runs this scraper automatically.

## Rises Scraper

The `rises_scraper.py` script collects gacha information from [rises.jp](https://rises.jp/product). It uses Playwright to scrape the listing page and extracts the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.
## Tora Net Oripa Scraper

The `tora_net_oripa_scraper.py` script collects gacha information from [tora.net-oripa.com](https://tora.net-oripa.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<SPREADSHEET_URL>
python rises_scraper.py
```

If scraping fails, the page HTML is saved to `rises_debug.html` for inspection.

The workflow `.github/workflows/scrape_rises.yml` runs this scraper automatically.

python rises_scraper.py
```

The workflow `.github/workflows/scrape_rises.yml` runs this scraper automatically.

export SPREADSHEET_URL=<YOUR_SHEET_URL>
python tora_net_oripa_scraper.py
```

The workflow `.github/workflows/scrape_tora_net_oripa.yml` runs this scraper automatically.

## Gachaking Oripa Scraper

The `gachaking_oripa_scraper.py` script collects gacha information from [gachaking-oripa.com](https://gachaking-oripa.com/index). It uses Playwright to scrape the listing page and gathers the title, image URL, detail page URL and PT value. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python gachaking_oripa_scraper.py
```

The workflow `.github/workflows/scrape_gachaking_oripa.yml` runs this scraper automatically.

## TCGShopAAA Scraper

The `tcgshopaaa_scraper.py` script collects gacha information from [tcgshopaaa.com](https://tcgshopaaa.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python tcgshopaaa_scraper.py
```

The workflow `.github/workflows/scrape_tcgshopaaa.yml` runs this scraper automatically.

## TCGShopAAA Banner Scraper

The `tcgshopaaa_banner_scraper.py` script retrieves banner image URLs from [tcgshopaaa.com](https://tcgshopaaa.com/). It uses Playwright to collect the image URL from the top page slider (`#sliderContainer`) and appends the image URL and site URL to the `news` sheet while skipping entries with a duplicate image URL.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python tcgshopaaa_banner_scraper.py
```

The workflow `.github/workflows/scrape_tcgshopaaa_banner.yml` runs this scraper automatically.
## Pokepa365 Scraper

The `pokepa365_scraper.py` script collects gacha information from [pokepa365.com](https://pokepa365.com/index). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python pokepa365_scraper.py
```

The workflow `.github/workflows/scrape_pokepa365.yml` runs this scraper automatically.

## Pokepa365 Banner Scraper

The `pokepa365_banner_scraper.py` script retrieves banner image URLs from [pokepa365.com](https://pokepa365.com/index). It uses Playwright to cycle through the top page slider and appends the image URL and site URL to the `news` sheet while skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python pokepa365_banner_scraper.py
```

The workflow `.github/workflows/scrape_pokepa365_banner.yml` runs this scraper automatically.

## Kagura TCG Scraper

The `kagura_tcg_scraper.py` script collects gacha information from [kagura-tcg.com](https://kagura-tcg.com/). It uses Playwright to scrape the top page and gathers the title, image URL, detail page URL and PT value from each entry. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
playwright install
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python kagura_tcg_scraper.py
```

The workflow `.github/workflows/scrape_kagura.yml` runs this scraper automatically.

## Quest Oripa Scraper

The `quest_oripa_scraper.py` script gathers gacha information from [quest-oripa.com](https://quest-oripa.com/). It uses Playwright to scrape the top page and collects the title, image URL, detail page URL and PT value from each entry. If an item lacks a visible title, the script falls back to the `identification_number` hidden field so that each row has a unique title. Detail URLs are extracted from either the link element or built from that identifier. New rows are appended to the `その他` sheet while skipping entries with duplicate URLs.

Run locally:

```bash
pip install -r requirements.txt
playwright install
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python quest_oripa_scraper.py
```

The workflow `.github/workflows/scrape_quest_oripa.yml` runs this scraper automatically.

## Cardel Scraper

The `cardel_scraper.py` script collects pack data from [cardel.online](https://cardel.online/). It uses Playwright to scrape the top page and appends the title, image URL, detail page URL and PT value to the `その他` sheet, skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
python -m playwright install
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python cardel_scraper.py
```

The workflow `.github/workflows/scrape_cardel.yml` runs this scraper automatically.

## Gtchaxonline Scraper

The `gtchaxonline_scraper.py` script collects gacha information from [gtchaxonline.com](https://gtchaxonline.com/). It uses Playwright to scrape the top page, waiting for dynamic elements to load. If a detail URL is not directly available, the script clicks the item and uses the resulting page URL. New rows containing the title, image URL, detail URL and PT value are appended to the `その他` sheet while skipping duplicates.

Run locally:

```bash
pip install -r requirements.txt
python -m playwright install
export GSHEET_JSON=<BASE64_SERVICE_ACCOUNT_JSON>
export SPREADSHEET_URL=<YOUR_SHEET_URL>
python gtchaxonline_scraper.py
```

The workflow `.github/workflows/scrape_gtchaxonline.yml` runs this scraper automatically.
