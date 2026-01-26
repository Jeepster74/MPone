import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from deep_translator import GoogleTranslator
import os
import re
from datetime import datetime, timedelta

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
BATCH_SIZE = 50 # Larger batch for SIM expansion
HEADLESS = True

# Keywords for sentiment analysis
MANAGEMENT_KEYWORDS = ['staff', 'old', 'dirty', 'service', 'rude', 'manager']
STRUCTURAL_KEYWORDS = ['layout', 'small', 'track', 'boring', 'slow', 'karts']

def translate_to_english(text, source_lang='auto'):
    try:
        if not text or text == "N/A":
            return text
        return GoogleTranslator(source=source_lang, target='en').translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

async def get_google_maps_data(page, location_name, city, country):
    city_str = str(city) if pd.notna(city) else ""
    search_query = f"{location_name} {city_str} {country}"
    print(f"Searching for: {search_query}")
    
    try:
        # Go to Google Maps with hl=en to force English UI
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Handle Cookie Consent
        if "consent.google.com" in page.url or await page.query_selector('form[action*="consent"]'):
            print("On consent page. Attempting to accept...")
            # More specific selector found by subagent
            consent_btn = await page.query_selector('button[aria-label="Accept all"]')
            if not consent_btn:
                # Fallback to locator-based search
                consent_btn_loc = page.get_by_role("button", name="Accept all").first
                if await consent_btn_loc.count() > 0:
                    consent_btn = consent_btn_loc
            
            if consent_btn:
                await consent_btn.click()
                print("Clicked Accept All. Waiting for redirect...")
                await page.wait_for_timeout(5000) # Wait for redirect back to maps
            else:
                print("Could not find Accept all button.")

        # Handle potential redirects/navigation states
        await page.wait_for_timeout(2000)
        
        # Check if we are stuck on a search results page
        if "google.com/maps/search/" in page.url and "/maps/place/" not in page.url:
            print(f"Search list detected: {page.url}")
            # Try various result selectors
            result_selectors = [
                'a.hfpxzc', 
                'a[href*="/maps/place/"]',
                'div[role="feed"] a',
                'div[aria-label*="Results for"] a'
            ]
            
            first_result = None
            for sel in result_selectors:
                try:
                    # Very short timeout as we want to fail fast and check URL again
                    first_result = await page.wait_for_selector(sel, timeout=2000)
                    if first_result: 
                        print(f"Found result with selector: {sel}")
                        break
                except: continue
            
            if first_result:
                await first_result.click()
                await page.wait_for_timeout(5000) # Wait for place page
            else:
                # One last check: did we redirect while waiting for selectors?
                if "/maps/place/" not in page.url:
                    print(f"No results found for query. URL: {page.url}")
                    await page.screenshot(path=f"debug_{location_name.replace(' ', '_')}.png")
                    return None

        # Final stabilization check
        for _ in range(5):
            if "/maps/place/" in page.url: break
            await page.wait_for_timeout(1000)

        # Now we should be on the place page.
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
        
        # Verify we are on a place page
        if "/maps/place/" not in page.url:
            print(f"Warning: URL does not look like a place page: {page.url}")

        # Hero Image extraction
        hero_img = await page.query_selector('button[aria-label^="Photo of"] img')
        if not hero_img:
            hero_img = await page.query_selector('img[src^="https://lh5.googleusercontent.com/p/"]')
            
        if hero_img:
            data['Hero Image URL'] = await hero_img.get_attribute('src')

        # Website extraction
        website_link = await page.query_selector('a[data-item-id="authority"]')
        if not website_link:
            website_link = await page.query_selector('a[aria-label^="Website:"]')
            
        if website_link:
            href = await website_link.get_attribute('href')
            # Clean Google redirect URL if present
            if "/url?q=" in href:
                import urllib.parse
                parsed = urllib.parse.urlparse(href)
                query = urllib.parse.parse_qs(parsed.query)
                if 'q' in query:
                    href = query['q'][0]
            data['Official Website'] = href
        
        # Reviews Section
        try:
            # Try clicking Reviews tab
            reviews_btn = await page.query_selector('button[aria-label*="Reviews"]')
            if not reviews_btn:
                tabs = await page.query_selector_all('button[role="tab"]')
                for tab in tabs:
                    text = await tab.inner_text()
                    if "Reviews" in text:
                        reviews_btn = tab
                        break
            
            if reviews_btn:
                await reviews_btn.click()
                await page.wait_for_timeout(3000)
                
                # Sort by Newest to get accurate velocity
                try:
                    sort_btn = await page.query_selector('button[aria-label="Sort reviews"]')
                    if sort_btn:
                        await sort_btn.click()
                        await page.wait_for_timeout(1000)
                        # The second option is usually "Newest" (the first is "Most relevant")
                        newest_opt = await page.query_selector('div[role="menuitemradio"]:nth-child(2)')
                        if newest_opt:
                            await newest_opt.click()
                            print("Sorted reviews by Newest.")
                            await page.wait_for_timeout(2000)
                except Exception as se:
                    print(f"Sorting error: {se}")
            else:
                btn_loc = page.get_by_role("button", name="Reviews").first
                if await btn_loc.count() > 0:
                    await btn_loc.click()
                    await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Reviews tab error: {e}")

        # Scrape reviews
        review_elements = await page.query_selector_all('div.jftiEf')
        print(f"Found {len(review_elements)} reviews on page.")
        
        if not review_elements:
            return data
            
        top_5_texts = []
        velocity = 0
        owner_replied = False
        
        for i, review in enumerate(review_elements):
            date_element = (await review.query_selector('.rsqawe') or 
                            await review.query_selector('.rsqaWe') or 
                            await review.query_selector('.rsqaUe'))
            
            date_text = await date_element.inner_text() if date_element else ""
            
            if date_text:
                dt_low = date_text.lower()
                if any(x in dt_low for x in ["month", "week", "day", "hour", "minute"]):
                    velocity += 1
                elif "year" not in dt_low:
                    velocity += 1
            
            if i < 5:
                # Expand
                see_more = await review.query_selector('button.w8nwRe')
                if see_more: 
                    await see_more.click()
                    await page.wait_for_timeout(500)
                
                text_element = (await review.query_selector('.wiI7pd') or 
                                await review.query_selector('.wiI7ic') or
                                await review.query_selector('.wiI79'))
                
                text = await text_element.inner_text() if text_element else ""
                if text:
                    # Sanitize: replace newlines with spaces
                    clean_text = text.replace('\n', ' ').replace('\r', ' ')
                    top_5_texts.append(clean_text)
                
                response = await review.query_selector('div.C76HXb')
                if response:
                    owner_replied = True
        
        print(f"Extracted {len(top_5_texts)} review texts. Velocity: {velocity}")
        
        # Analysis
        translated = []
        m_issues = False
        s_issues = False
        
        for t in top_5_texts:
            if not t: continue
            en_t = translate_to_english(t).lower()
            translated.append(en_t)
            if any(k in en_t for k in MANAGEMENT_KEYWORDS): m_issues = True
            if any(k in en_t for k in STRUCTURAL_KEYWORDS): s_issues = True
        
        data['Review Velocity (12m)'] = velocity
        data['Management Issues'] = m_issues
        data['Structural Issues'] = s_issues
        data['Owner Activity'] = owner_replied
        data['Top Reviews Snippet'] = " | ".join(translated[:3])
            
        return data
        
    except Exception as e:
        print(f"Error scraping {location_name}: {e}")
        return None
        
    except Exception as e:
        print(f"Error scraping {location_name}: {e}")
        return None
        
    except Exception as e:
        print(f"Error scraping {location_name}: {e}")
        return None

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Initialize new columns
    new_cols = [
        'Review Velocity (12m)', 'Hero Image URL', 'Management Issues', 
        'Structural Issues', 'Owner Activity', 'Top Reviews Snippet',
        'Maps URL', 'Official Website'
    ]
    for col in new_cols:
        if col not in df.columns:
            df[col] = "N/A"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        page = await context.new_page()
        
        processed_count = 0
        for index, row in df.iterrows():
            # Skip if already enriched (not NaN, not N/A, not FAILED, not empty)
            val = str(row['Review Velocity (12m)'])
            if val not in ["N/A", "nan", "FAILED", ""]:
                continue
                
            res = await get_google_maps_data(page, row['Name'], row['City'], row['Country'])
            if res:
                for k, v in res.items():
                    df.at[index, k] = v
                processed_count += 1
                
                # Save progress every 10 locations for better performance during full run
                if processed_count % 10 == 0:
                    df.to_csv(OUTPUT_FILE, index=False)
                    print(f"Saved progress after {processed_count} locations.")
            else:
                # Mark as failed to avoid retrying if explicitly failed
                df.at[index, 'Review Velocity (12m)'] = "FAILED"
                df.to_csv(OUTPUT_FILE, index=False)
                
            await asyncio.sleep(1) # Small delay
            
        await browser.close()
    
    print(f"Enrichment complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
