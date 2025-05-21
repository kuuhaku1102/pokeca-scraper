import os
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import base64
import json

def strip_query_params(url: str) -> str:
  """Removes query parameters from a URL."""
  parsed = urlparse(url)
  return parsed.scheme + "://" + parsed.netloc + parsed.path

if __name__ == "__main__":
  print("Connecting to Google Sheets...")
  scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
  
  try:
    gsheet_json_str = os.environ['GSHEET_JSON']
  except KeyError:
    print("Error: GSHEET_JSON environment variable not set.")
    exit(1)

  try:
    # Try decoding if it's base64 encoded
    credentials_dict = json.loads(base64.b64decode(gsheet_json_str))
  except (TypeError, ValueError, json.JSONDecodeError):
    # Assume it's plain JSON if decoding fails
    try:
      credentials_dict = json.loads(gsheet_json_str)
    except json.JSONDecodeError as e:
      print(f"Error: Could not parse GSHEET_JSON: {e}")
      exit(1)

  try:
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    spreadsheet_url = os.environ.get("SPREADSHEET_URL")
    if not spreadsheet_url:
      print("Error: SPREADSHEET_URL environment variable not set.")
      exit(1)
    
    spreadsheet = gc.open_by_url(spreadsheet_url)
    sheet = spreadsheet.worksheet("その他")
    print("Successfully connected to worksheet 'その他'")

    # Fetch existing detail URLs
    print("Fetching existing detail URLs from the sheet...")
    existing_detail_urls = set()
    try:
      all_rows = sheet.get_all_values()
      if not all_rows:
        print("The 'その他' sheet is empty.")
      else:
        for row_index, row in enumerate(all_rows[1:]): # Skip header row
          if len(row) > 2 and row[2]: # Check if URL column exists and is not empty
            url = row[2]
            normalized_url = strip_query_params(url)
            existing_detail_urls.add(normalized_url)
          elif len(row) <=2 and row_index > 0 : # only print warning if it's not the header and not empty
             print(f"Warning: Row {row_index + 2} has less than 3 columns or the URL is empty. Skipping.")
        print(f"Found {len(existing_detail_urls)} existing detail URLs in the sheet.")
    except Exception as e:
      print(f"An error occurred while fetching existing URLs: {e}")
      # Decide if you want to exit or continue. For now, let's continue.
      # exit(1) 

  except gspread.exceptions.SpreadsheetNotFound:
    print(f"Error: Spreadsheet not found at URL: {spreadsheet_url}")
    exit(1)
  except gspread.exceptions.WorksheetNotFound:
    print(f"Error: Worksheet 'その他' not found in the spreadsheet.")
    exit(1)
  except Exception as e:
    print(f"An unexpected error occurred during Google Sheets connection: {e}")
    exit(1)

  print("Starting Playwright scraping logic...")
  scraped_data = []
  
  try:
    with sync_playwright() as p:
      browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
      page = browser.new_page()
      
      print("Navigating to https://moshoripa.com/ ...")
      page.goto("https://moshoripa.com/", timeout=60000, wait_until="networkidle")
      print("Page navigation successful.")
      
      print("Waiting for gacha cards to load...")
      page.wait_for_selector("div.homes-gacha-card", timeout=60000)
      print("Gacha cards loaded.")
      
      print("Extracting data from page...")
      items = page.evaluate('''() => {
        const cards = Array.from(document.querySelectorAll('div.homes-gacha-card'));
        return cards.map(card => {
          const detail_url_element = card.querySelector('a.gacha-link');
          const detail_url = detail_url_element ? detail_url_element.href : null;
          
          const image_element = card.querySelector('a.gacha-link > img');
          const image_url = image_element ? image_element.src : null;
          
          let title = detail_url_element ? detail_url_element.textContent.trim() : '';
          if (!title || title.length < 2) { // Check if title is empty or mostly whitespace
            title = image_element ? image_element.alt.trim() : 'No title';
          }
          if (!title) title = 'No title';


          const pt_element = card.querySelector('div.gacha-price span.font-size-xl');
          const pt = pt_element ? pt_element.textContent.trim() : '0';
          
          return { title, image_url, detail_url, pt };
        });
      }''')
      
      print(f"Found {len(items)} items on the page.")
      
      for item in items:
        if item['image_url'] and item['image_url'].startswith('/'):
          item['image_url'] = f"https://moshoripa.com{item['image_url']}"
        if item['detail_url'] and item['detail_url'].startswith('/'):
          item['detail_url'] = f"https://moshoripa.com{item['detail_url']}"
        
        scraped_data.append([
          item['title'], 
          item['image_url'], 
          item['detail_url'], 
          item['pt']
        ])
        
      browser.close()
      print("Browser closed.")
      
  except Exception as e:
    print(f"An error occurred during Playwright scraping: {e}")
    if 'page' in locals() and page:
      try:
        page_content = page.content()
        with open("moshoripa_debug.html", "w", encoding="utf-8") as f:
          f.write(page_content)
        print("Page content saved to moshoripa_debug.html")
      except Exception as save_e:
        print(f"Could not save page content: {save_e}")
    if 'browser' in locals() and browser:
      browser.close()
      print("Browser closed due to error.")
    # Decide if you want to exit or continue. For now, let's add to scraped_data and continue
    # exit(1)

  print("Processing scraped data and appending to Google Sheets...")
  new_rows_to_append = []

  if not scraped_data:
    print("No data was scraped. Skipping processing and appending.")
  else:
    for item_index, item in enumerate(scraped_data):
      if not item or len(item) < 3:
        print(f"Warning: Scraped item at index {item_index} is malformed or None. Skipping. Data: {item}")
        continue

      detail_url = item[2]
      if not detail_url:
        print(f"Warning: Scraped item '{item[0]}' (index {item_index}) has no detail_url. Skipping.")
        continue
      
      normalized_url = strip_query_params(detail_url)
      
      if normalized_url not in existing_detail_urls:
        new_rows_to_append.append(item)
        print(f"✅ Adding new item: {item[0]}")
      else:
        print(f"⏭ Skipping duplicate: {item[0]} - {detail_url}")
        
    if new_rows_to_append:
      print(f"Attempting to append {len(new_rows_to_append)} new items to the sheet...")
      try:
        sheet.append_rows(new_rows_to_append, value_input_option='USER_ENTERED')
        print(f"📥 Appended {len(new_rows_to_append)} new items to the sheet.")
      except Exception as e:
        print(f"An error occurred while appending rows to Google Sheets: {e}")
    else:
      print("📭 No new data to append.")
  
  print("Script finished.")
