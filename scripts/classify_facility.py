import pandas as pd
import os
import json
import asyncio
from playwright.async_api import async_playwright
import re

# Resolve paths relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
KEYWORDS_FILE = os.path.join(SCRIPT_DIR, "classify_keywords.json")

# Weights (Confidence scores out of 1.0)
WEIGHTS = {
    "web": 0.5,
    "osm": 0.3,
    "footprint": 0.1,
    "sentiment": 0.1
}

def load_keywords():
    with open(KEYWORDS_FILE, 'r') as f:
        return json.load(f)

async def check_website(url, keywords):
    if not url or pd.isna(url) or url == "N/A" or not str(url).startswith("http"):
        return {"is_indoor": False, "is_outdoor": False, "is_sim": False}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            content = (await page.content()).lower()
            
            res = {"is_indoor": False, "is_outdoor": False, "is_sim": False}
            
            # Simple keyword presence
            for lang in keywords["indoor"]:
                if any(kw in content for kw in keywords["indoor"][lang]): res["is_indoor"] = True
            for lang in keywords["outdoor"]:
                if any(kw in content for kw in keywords["outdoor"][lang]): res["is_outdoor"] = True
            for lang in keywords["sim"]:
                if any(kw in content for kw in keywords["sim"][lang]): res["is_sim"] = True
                
            await browser.close()
            return res
    except:
        return {"is_indoor": False, "is_outdoor": False, "is_sim": False}

def classify_by_footprint(sqm):
    try:
        sqm = float(sqm)
        # Indoor karts typically operate in 1,000 - 6,000 sqm warehouses.
        # Sites > 10,000 sqm are likely entire outdoor circuit grounds.
        if sqm > 1000 and sqm < 10000: return "Indoor"
        if sqm >= 10000: return "Outdoor" # Massive polygon = likely ground footprint
        if sqm < 300 and sqm > 0: return "Small" # Skip tiny/storage buildings
        return None
    except:
        return None

def get_scores(text, keywords):
    if not text or pd.isna(text) or str(text) == "N/A":
        return {"indoor": 0, "outdoor": 0, "sim": 0}
    
    text = str(text).lower()
    scores = {"indoor": 0, "outdoor": 0, "sim": 0}
    
    for category in ["indoor", "outdoor", "sim"]:
        for lang in keywords[category]:
            for kw in keywords[category][lang]:
                if kw in text: scores[category] += 1
    return scores

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("Loading track data...")
    df = pd.read_csv(INPUT_FILE)
    keywords = load_keywords()

    # Initialize new flag columns
    for col in ['is_indoor', 'is_outdoor', 'is_sim']:
        if col not in df.columns:
            df[col] = False

    print(f"Classifying {len(df)} locations (Multi-label)...")

    # For SIM detection, we should be slightly more aggressive with the Website check 
    # for tracks that don't have SIM in the name.
    
    for index, row in df.iterrows():
        # Reset flags for fresh evaluation
        df.at[index, 'is_indoor'] = False
        df.at[index, 'is_outdoor'] = False
        df.at[index, 'is_sim'] = False

        name = str(row['Name']).lower()
        snippet = str(row['Top Reviews Snippet']).lower()
        
        # 1. Check Name & Category
        cat = str(row['Category']).lower()
        if "sim racing" in cat or "sim" in name: df.at[index, 'is_sim'] = True
        if "indoor" in name: df.at[index, 'is_indoor'] = True
        if "outdoor" in name or "circuit" in name: df.at[index, 'is_outdoor'] = True
            
        # 2. Footprint indicators
        fp_type = classify_by_footprint(row['building_sqm'])
        if fp_type == "Indoor": df.at[index, 'is_indoor'] = True
        elif fp_type == "Outdoor": df.at[index, 'is_outdoor'] = True
        
        # 3. Sentiment/Reviews Analysis
        scores = get_scores(snippet, keywords)
        if scores["indoor"] > 0: df.at[index, 'is_indoor'] = True
        if scores["outdoor"] > 0: df.at[index, 'is_outdoor'] = True
        if scores["sim"] > 0: df.at[index, 'is_sim'] = True
        
        # 4. Final cleaning: if name has "SIM" but no other indicator, is_sim is true
        if "sim" in name: df.at[index, 'is_sim'] = True

    # Drop old facility_type if exists to avoid confusion
    if 'facility_type' in df.columns:
        df = df.drop(columns=['facility_type'])

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Multi-label classification complete. Results saved to {OUTPUT_FILE}")

    # Summary
    print("\nClassification Statistics:")
    print(f"Indoor:  {df['is_indoor'].sum()}")
    print(f"Outdoor: {df['is_outdoor'].sum()}")
    print(f"SIM:     {df['is_sim'].sum()}")
    print(f"Hybrid (In/Out): {len(df[df['is_indoor'] & df['is_outdoor']])}")

if __name__ == "__main__":
    asyncio.run(main())
