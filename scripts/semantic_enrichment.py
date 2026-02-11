import asyncio
import os
import pandas as pd
import json
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import google.generativeai as genai

# Setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_semantically_enriched.csv")

# Load Env
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

async def scrape_text(url):
    """Scrapes visible text from a website, visiting key pages if found."""
    if not url or pd.isna(url) or "http" not in str(url):
        return ""
    
    print(f"  [Scraper] Visiting {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
            page = await context.new_page()
            
            # 1. Visit Homepage
            try:
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            except:
                print(f"    -> Failed to load {url}")
                await browser.close()
                return ""

            # Extract homepage text
            content = await page.inner_text("body")
            
            # 2. Look for "Topic" links (Track, Strecke, Piste, About, Infos)
            # We look for links that might contain technical data
            links = await page.eval_on_selector_all("a", "elements => elements.map(e => ({href: e.href, text: e.innerText}))")
            
            # Multilingual keywords for navigation (English, German, French, Dutch)
            keywords = [
                # English
                "track", "circuit", "layout", "about", "facts", "info", 
                # German
                "strecke", "bahn", "bahndaten", "fakten", "über uns", "infos", "länge",
                # French
                "piste", "tracé", "longueur", "a propos", "infos", "circuit",
                # Dutch
                "baan", "lengte", "over ons", "informatie",
                # General
                "technical", "technische", "donnees", "gegevens"
            ]
            subpages_visited = 0
            
            for link in links:
                if subpages_visited >= 3: break # Max 3 subpages (increased from 2)
                
                href = link.get("href")
                text = link.get("text", "").lower()
                
                # If link matches keyword and is internal
                if href and any(kw in text for kw in keywords) and url in href:
                    print(f"    -> Visiting subpage: {text} ({href})")
                    try:
                        await page.goto(href, timeout=10000, wait_until="domcontentloaded")
                        sub_content = await page.inner_text("body")
                        content += "\n\n --- SUBPAGE: " + text + " ---\n" + sub_content
                        subpages_visited += 1
                    except:
                        pass
                        
            await browser.close()
            return content[:15000] # Limit context size
    except Exception as e:
        print(f"  [Scraper] Error: {e}")
        return ""

def analyze_with_gemini(info_text, reviews_text, facility_name):
    """Asks Gemini to extract technical data from the raw text."""
    
    prompt = f"""
    You are a Data Extraction Expert. 
    Analyze the provided WEBSITE CONTENT and CUSTOMER REVIEWS for the karting facility: "{facility_name}".
    
    GOAL: Extract precision data about the track.
    
    DATA SOURCES:
    1. WEBSITE CONTENT:
    {info_text[:10000]}
    
    2. REVIEWS:
    {reviews_text[:5000]}
    
    TASK:
    Return a JSON object with these fields:
    - "length_meters": (integer) The track length in meters. If multiple tracks, chose the main adult track. If unknown, null.
    - "is_indoor": (boolean)
    - "is_outdoor": (boolean)
    - "is_multilevel": (boolean)
    - "confidence": (string) "High", "Medium", "Low"
    - "source": (string) "Website" or "Reviews" or "Both"
    - "reasoning": (string) Short explanation of where the number came from (e.g. "Website 'About' page says 600m").
    
    IMPORTANT: 
    - Be skeptical. If reviews say "small track" but website says "1000m", note the conflict but prefer the official website number unless it looks like a lie.
    - If there are clearly TWO tracks (Indoor and Outdoor), set both flags to true.
    
    JSON OUTPUT ONLY:
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except Exception as e:
        print(f"  [Gemini] Error: {e}")
        return None

async def main():
    print("Loading data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Load existing results if any to skip processed
    processed_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(OUTPUT_FILE)
            if 'track_id' in existing_df.columns:
                processed_ids = set(existing_df['track_id'].unique())
            print(f"resuming... Found {len(processed_ids)} already processed.")
        except:
            pass
            
    # filter out processed
    to_process = df[~df['track_id'].isin(processed_ids)].copy()
    
    # Prioritize: 
    # 1. Fahr-Werk (ID 366)
    # 2. Missing Length (0 or NaN)
    # 3. Everything else
    
    # Create priority flag
    to_process['is_priority'] = to_process['Name'].str.contains("Fahr-Werk", case=False, na=False) | (to_process['track_length_m'].isna()) | (to_process['track_length_m'] == 0)
    to_process = to_process.sort_values('is_priority', ascending=False)
    
    # Batch limit (process all remaining)
    BATCH_SIZE = 2000
    to_process = to_process.head(BATCH_SIZE)
    
    print(f"Processing batch of {len(to_process)} targets...")
    
    results = []
    
    for index, row in to_process.iterrows():
        name = row['Name']
        url = row['Official Website']
        track_id = row['track_id']
        reviews = str(row.get('Top Reviews Snippet', ''))
        if reviews.lower() == 'nan': reviews = ""
        
        print(f"\nAnalyzing [{index}/{len(to_process)}]: {name} ({url})")
        
        # 1. Scrape
        web_text = await scrape_text(url)
        
        # 2. Analyze
        if not web_text and not reviews:
            print("  -> No data to analyze.")
            # Record as failed/empty to avoid reprocessing loop? 
            # For now, just skip logic, but maybe we should record "attempted"?
            # We'll save a minimal record.
            result_row = {
                "track_id": track_id,
                "Name": name,
                "ai_length": None,
                "ai_indoor": None, 
                "ai_outdoor": None,
                "reasoning": "No data available (scrape failed, no reviews)"
            }
        else:
            data = analyze_with_gemini(web_text, reviews, name)
            if data:
                print("  -> RESULT:", json.dumps(data, indent=2))
                result_row = {
                    "track_id": track_id,
                    "Name": name,
                    "ai_length": data.get("length_meters"),
                    "ai_indoor": data.get("is_indoor"),
                    "ai_outdoor": data.get("is_outdoor"),
                    "reasoning": data.get("reasoning")
                }
            else:
                result_row = {
                    "track_id": track_id,
                    "Name": name,
                    "ai_length": None,
                    "ai_indoor": None,
                    "ai_outdoor": None,
                    "reasoning": "Gemini analysis failed"
                }

        results.append(result_row)
        
        # Incremental Save
        if len(results) >= 5:
            save_results(results)
            results = [] # Clear buffer
            
    # Final save
    if results:
        save_results(results)

def save_results(results):
    if not results: return
    new_df = pd.DataFrame(results)
    
    if os.path.exists(OUTPUT_FILE):
        # Append without header
        new_df.to_csv(OUTPUT_FILE, mode='a', header=False, index=False)
    else:
        new_df.to_csv(OUTPUT_FILE, index=False)

if __name__ == "__main__":
    # Redefine save logic inline to be simpler
    pass 
    asyncio.run(main())
