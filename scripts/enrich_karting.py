import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from deep_translator import GoogleTranslator
import os
import re
import argparse
import math
from datetime import datetime, timedelta
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)
from validate_karting import is_valid_karting

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
DEFAULT_BATCH_SIZE = 50 
DEFAULT_HEADLESS = True

# Keywords for sentiment analysis
MANAGEMENT_KEYWORDS = ['staff', 'old', 'dirty', 'service', 'rude', 'manager']
STRUCTURAL_KEYWORDS = ['layout', 'small', 'track', 'boring', 'slow', 'karts']

# Localized search terms for recovery
LOCAL_KEYWORDS = {
    'Netherlands': 'Kartbaan',
    'Belgium': 'Karting',
    'Germany': 'Kartbahn',
    'France': 'Circuit de Karting',
    'United Kingdom': 'Go Karting'
}

def translate_to_english(text, source_lang='auto'):
    try:
        if not text or text == "N/A":
            return text
        return GoogleTranslator(source=source_lang, target='en').translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def safe_save(df, output_file):
    """
    Reloads the CSV from disk, merges updates, and saves to prevent overwriting 
    concurrent changes from other scripts (like enrich_reach.py).
    """
    try:
        if os.path.exists(output_file):
            disk_df = pd.read_csv(output_file)
            # Use track_id as index for merging
            disk_df.set_index('track_id', inplace=True)
            df_temp = df.set_index('track_id')
            
            # Update disk_df with values from df_temp
            disk_df.update(df_temp)
            disk_df.reset_index().to_csv(output_file, index=False)
        else:
            df.to_csv(output_file, index=False)
        print(f"--- Concurrency-Safe Save Complete ---")
    except Exception as e:
        print(f"Error during safe save: {e}")

async def get_google_maps_data(page, location_name, city, country, lat=None, lon=None):
    is_recovery = False
    if pd.isna(location_name) or str(location_name).lower() in ["nan", "n/a", "sim"]:
        is_recovery = True
        # "karting near" is the most reliable pattern for nameless coordinate nodes
        search_query = f"karting near {lat}, {lon}"
    else:
        city_str = str(city) if pd.notna(city) else ""
        search_query = f"{location_name} {city_str} {country}"
    
    print(f"Searching for: {search_query}")
    
    try:
        if is_recovery:
            # Use @lat,lon to anchor the map geographically
            url = f"https://www.google.com/maps/search/karting/@{lat},{lon},15z?hl=en"
        else:
            url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
            
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000) # Increased timeout for map anchoring
        
        # Handle Cookie Consent
        if "consent.google.com" in page.url or await page.query_selector('form[action*="consent"]'):
            consent_btn = await page.query_selector('button[aria-label="Accept all"]')
            if not consent_btn:
                consent_btn_loc = page.get_by_role("button", name="Accept all").first
                if await consent_btn_loc.count() > 0:
                    consent_btn = consent_btn_loc
            
            if consent_btn:
                await consent_btn.click()
                await page.wait_for_timeout(5000)

        # Handle redirects/search list
        await page.wait_for_timeout(2000)
        if "google.com/maps/search/" in page.url and "/maps/place/" not in page.url:
            result_selectors = ['a.hfpxzc', 'a[href*="/maps/place/"]']
            for sel in result_selectors:
                try:
                    first_result = await page.wait_for_selector(sel, timeout=3000)
                    if first_result: 
                        await first_result.click()
                        await page.wait_for_timeout(5000)
                        break
                except: continue

        if "/maps/place/" not in page.url:
            return None

        # Extract Data
        data = {
            'Maps URL': page.url,
            'Review Velocity (12m)': 0,
            'Hero Image URL': "N/A",
            'Management Issues': False,
            'Structural Issues': False,
            'Owner Activity': False,
            'Top Reviews Snippet': "N/A",
            'Official Website': "N/A"
        }

        # Recover Name if missing
        if is_recovery:
            name_elem = await page.query_selector('h1.DUwDvf')
            cat_elem = await page.query_selector('button[jsaction*="category"] span')
            
            recovered_name = await name_elem.inner_text() if name_elem else "N/A"
            recovered_cat = await cat_elem.inner_text() if cat_elem else "N/A"
            
            # Distance Sanity Check: Extract coords from URL
            # Format: .../@lat,lon,zoom...
            match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', page.url)
            if match:
                res_lat, res_lon = float(match.group(1)), float(match.group(2))
                dist = math.sqrt((res_lat - lat)**2 + (res_lon - lon)**2)
                # Roughly 0.5 degrees (~50km) max distance for recovery
                if dist > 0.5:
                    print(f"Geographic mismatch: {recovered_name} is too far ({dist:.2f} units). Skipping.")
                    return None

            # Use the new strict validation
            if not is_valid_karting(recovered_name, recovered_cat):
                print(f"Validation failed for: {recovered_name} ({recovered_cat}). Skipping.")
                return None
                
            data['Name'] = recovered_name
            data['Category'] = "Karting" # Default to Karting for recovered tracks
            print(f"Recovered & Validated: {recovered_name}")

        hero_img = await page.query_selector('button[aria-label^="Photo of"] img')
        if hero_img:
            data['Hero Image URL'] = await hero_img.get_attribute('src')

        website_link = await page.query_selector('a[data-item-id="authority"]')
        if website_link:
            href = await website_link.get_attribute('href')
            data['Official Website'] = href
        
        # Reviews
        try:
            reviews_btn = await page.query_selector('button[aria-label*="Reviews"]')
            if reviews_btn:
                await reviews_btn.click()
                await page.wait_for_timeout(3000)
        except: pass

        review_elements = await page.query_selector_all('div.jftiEf')
        if review_elements:
            top_5_texts = []
            velocity = 0
            owner_replied = False
            for i, review in enumerate(review_elements):
                date_element = await review.query_selector('.rsqawe')
                date_text = await date_element.inner_text() if date_element else ""
                if date_text and any(x in date_text.lower() for x in ["month", "week", "day"]):
                    velocity += 1
                
                if i < 5:
                    text_element = await review.query_selector('.wiI7pd')
                    text = await text_element.inner_text() if text_element else ""
                    if text: top_5_texts.append(text.replace('\n', ' '))
                    if await review.query_selector('div.C76HXb'): owner_replied = True
            
            translated = [translate_to_english(t).lower() for t in top_5_texts]
            data['Review Velocity (12m)'] = velocity
            data['Management Issues'] = any(any(k in t for k in MANAGEMENT_KEYWORDS) for t in translated)
            data['Structural Issues'] = any(any(k in t for k in STRUCTURAL_KEYWORDS) for t in translated)
            data['Owner Activity'] = owner_replied
            data['Top Reviews Snippet'] = " | ".join(translated[:3])
            
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    parser = argparse.ArgumentParser(description='Enrich karting data with Google Maps info.')
    parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_SIZE, help='Number of locations to process')
    parser.add_argument('--gui', action='store_true', help='Run with visible browser')
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Initialize new columns
    new_cols = ['Review Velocity (12m)', 'Hero Image URL', 'Management Issues', 'Structural Issues', 'Owner Activity', 'Top Reviews Snippet', 'Maps URL', 'Official Website']
    for col in new_cols:
        if col not in df.columns: df[col] = "N/A"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.gui)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Prioritize nameless (1) or missing image (2) records
        df['priority'] = df.apply(lambda r: 1 if pd.isna(r['Name']) or str(r['Name']).lower() in ["nan", "n/a"] else (2 if str(r['Hero Image URL']) in ["N/A", "nan", "FAILED", ""] else 3), axis=1)
        
        # Only process those that need enrichment
        to_process = df[df['priority'] < 3].sort_values('priority').head(args.batch)
        
        print(f"Processing {len(to_process)} priority locations (Target: {args.batch})...")

        processed_count = 0
        for index, row in to_process.iterrows():
            res = await get_google_maps_data(page, row['Name'], row['City'], row['Country'], row['Latitude'], row['Longitude'])
            if res:
                for k, v in res.items():
                    df.at[index, k] = v
                processed_count += 1
                if processed_count % 5 == 0:
                    safe_save(df.drop(columns=['priority']), OUTPUT_FILE)
            else:
                df.at[index, 'Review Velocity (12m)'] = "FAILED"
                safe_save(df.drop(columns=['priority']), OUTPUT_FILE)
            
            await asyncio.sleep(2)
            
        await browser.close()
    
    safe_save(df.drop(columns=['priority']), OUTPUT_FILE)
    print(f"Enrichment complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
