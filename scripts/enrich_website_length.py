import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import re
import os
import argparse
import time

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
DEFAULT_BATCH_SIZE = 20

# Regex patterns for track length
# Matches: 400m, 400 meter, 400 metres, length: 400, length of 400
LENGTH_PATTERNS = [
    r'(\d{2,4})\s?m(?!\w)',
    r'(\d{2,4})\s?meter',
    r'(\d{2,4})\s?metres',
    r'length:\s?(\d{2,4})',
    r'länge:\s?(\d{2,4})',
    r'longueur:\s?(\d{2,4})',
    r'lunghezza:\s?(\d{2,4})',
    r'lengte:\s?(\d{2,4})'
]

async def scrape_track_length(page, url):
    try:
        print(f"   Visiting: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # Get all text from body
        text = await page.inner_text('body')
        text = text.lower()
        
        found_lengths = []
        for pattern in LENGTH_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                val = int(match.group(1))
                # Sanity check: karting tracks are usually between 100m and 3000m
                if 100 <= val <= 3000:
                    found_lengths.append(val)
        
        if found_lengths:
            # Usually the largest number in this range is the main track length
            # (To avoid catching things like "100% fun" or "50m from station")
            best_guess = max(found_lengths)
            print(f"      Found potential length: {best_guess}m")
            return best_guess
            
        return None
    except Exception as e:
        print(f"      Error scraping {url}: {e}")
        return None

async def main():
    parser = argparse.ArgumentParser(description='Scrape track lengths from websites.')
    parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_SIZE, help='Batch size')
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    if 'website_track_length_m' not in df.columns:
        df['website_track_length_m'] = 0

    # Process records with a website but no website_track_length_m yet
    mask = (df['Official Website'].notna()) & (df['Official Website'] != 'N/A') & (df['website_track_length_m'] == 0)
    to_process = df[mask].head(args.batch)
    
    if to_process.empty:
        print("No websites to scrape.")
        return
        
    print(f"Scraping {len(to_process)} websites...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # We'll create a new page for each site to avoid cross-pollution
        
        processed_count = 0
        for index, row in to_process.iterrows():
            url = row['Official Website']
            print(f"[{processed_count+1}/{len(to_process)}] {row['Name']}")
            
            page = await browser.new_page()
            length = await scrape_track_length(page, url)
            await page.close()
            
            if length:
                df.at[index, 'website_track_length_m'] = length
            else:
                df.at[index, 'website_track_length_m'] = -1
            
            processed_count += 1
            if processed_count % 5 == 0:
                df.to_csv(OUTPUT_FILE, index=False)
                
        await browser.close()

    # Final save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nFinished scraping {processed_count} websites.")

if __name__ == "__main__":
    asyncio.run(main())
