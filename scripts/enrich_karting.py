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
MAX_SCROLL_ATTEMPTS = 10  # Scroll more to load more reviews

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
            
            # Ensure all columns from df exist in disk_df
            for col in df_temp.columns:
                if col not in disk_df.columns:
                    disk_df[col] = "N/A"
            
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
            
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(8000)  # Longer wait for proper loading
        
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
            'Official Website': "N/A",
            'Average Rating': 0.0
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
        
        # Extract Rating
        rating_elem = await page.query_selector('span[role="img"][aria-label*="stars"]')
        if rating_elem:
            label = await rating_elem.get_attribute('aria-label')
            match = re.search(r'(\d+\.\d+|\d+)', label)
            if match:
                data['Average Rating'] = float(match.group(1))
        
        # Reviews
        try:
            reviews_btn = await page.query_selector('button[aria-label*="Reviews"]')
            if reviews_btn:
                await reviews_btn.click()
                await page.wait_for_timeout(3000)
                
                # Scroll the review panel to load more reviews
                # Use more specific selector that works consistently
                review_panel = await page.query_selector('.m6QErb.DxyBCb.kA9KIf.dS8AEf')
                if not review_panel:
                    review_panel = await page.query_selector('.m6QErb.DxyBCb')
                if review_panel:
                    for scroll_attempt in range(MAX_SCROLL_ATTEMPTS):
                        await page.evaluate('el => el.scrollBy(0, 800)', review_panel)
                        await page.wait_for_timeout(1000)  # Longer wait for lazy loading
        except Exception as e:
            print(f"Review panel scroll error: {e}")

        review_elements = await page.query_selector_all('div.jftiEf')
        if review_elements:
            review_texts = []
            velocity = 0
            owner_replied = False
            total_reviews = len(review_elements)
            
            for i, review in enumerate(review_elements):
                # Try multiple selectors for date (Google Maps changes these)
                date_text = ""
                date_selectors = ['.rsqawe', '.DU9Pgb', 'span[class*="date"]', '.xRkPPb']
                for sel in date_selectors:
                    try:
                        date_element = await review.query_selector(sel)
                        if date_element:
                            date_text = await date_element.inner_text()
                            if date_text:
                                break
                    except:
                        continue
                
                # Check if review is recent (within 12 months)
                is_recent = date_text and any(x in date_text.lower() for x in ["month", "week", "day", "hour", "mois", "semaine", "jour", "heure", "monat", "woche", "tag"])
                
                if is_recent:
                    velocity += 1
                    
                    # Collect ALL review texts from last 12 months - no limit
                    text_element = await review.query_selector('.wiI7pd')
                    text = await text_element.inner_text() if text_element else ""
                    if text and len(text) > 20:  # Skip very short reviews
                        review_texts.append(text.replace('\n', ' '))
                
                # Check for owner replies
                if await review.query_selector('div.C76HXb'):
                    owner_replied = True
            
            # Translate collected reviews
            translated = [translate_to_english(t).lower() for t in review_texts]
            data['Review Velocity (12m)'] = velocity
            data['review_count_12m'] = len(review_texts)  # Actual count of captured reviews
            data['Management Issues'] = any(any(k in t for k in MANAGEMENT_KEYWORDS) for t in translated)
            data['Structural Issues'] = any(any(k in t for k in STRUCTURAL_KEYWORDS) for t in translated)
            data['Owner Activity'] = owner_replied
            data['Top Reviews Snippet'] = " | ".join(translated)  # Store ALL reviews for Gemini
            
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    parser = argparse.ArgumentParser(description='Enrich karting data with Google Maps info.')
    parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_SIZE, help='Number of locations to process')
    parser.add_argument('--gui', action='store_true', help='Run with visible browser')
    parser.add_argument('--force-all', action='store_true', help='Re-process ALL locations (ignore priority)')
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Initialize new columns
    new_cols = ['Review Velocity (12m)', 'Hero Image URL', 'Management Issues', 'Structural Issues', 'Owner Activity', 'Top Reviews Snippet', 'Maps URL', 'Official Website', 'Average Rating']
    for col in new_cols:
        if col not in df.columns: df[col] = "N/A"

    async with async_playwright() as p:
        # Launch with anti-detection settings
        browser = await p.chromium.launch(
            headless=not args.gui,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        # Prioritize: 1=missing snippet, 2=nameless/no rating, 3=complete
        def get_priority(r):
            snippet = str(r.get('Top Reviews Snippet', ''))
            has_snippet = len(snippet) > 10 and snippet != 'nan'
            if not has_snippet:
                return 1  # Missing review data
            if pd.isna(r['Name']) or str(r['Name']).lower() in ["nan", "n/a"]:
                return 2  # Nameless
            if str(r['Average Rating']) in ["N/A", "nan", "0.0", "0", ""]:
                return 2  # Missing rating
            return 3  # Complete
        
        df['priority'] = df.apply(get_priority, axis=1)
        
        # Select locations to process
        if args.force_all:
            # Process ALL locations when --force-all is used
            to_process = df.head(args.batch)
            print(f"FORCE-ALL MODE: Processing {len(to_process)} locations...")
        else:
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
