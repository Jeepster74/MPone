import pandas as pd
import os
import re

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# Negative keywords that imply the record isn't a functional karting/sim center
BAD_NAME_KEYWORDS = [
    r'\babandoned\b', r'\bprojet\b', r'\bancien\b', r'\brue du karting\b', 
    r'\baltissimo\b', r'\bclimbing\b', r'\bdining\b', r'\brestaurant\b',
    r'\bbowling\b', r'\blaser\b', r'\btag\b', r'\bpaintball\b'
]

# Positive keywords for trust boost
TRUSTED_NAME_KEYWORDS = [r'\bkarting\b', r'\bkarts\b', r'\bcircuit\b', r'\braceway\b', r'\btrack\b', r'\bsim\b', r'\bsimulation\b', r'\bracing\b']

def calculate_refined_score(row):
    score = 0
    name = str(row.get('Name', '')).lower()
    
    # 1. Image Presence (25 pts)
    img = str(row.get('Hero Image URL', 'N/A'))
    if img not in ['N/A', 'nan', 'FAILED', '']:
        score += 25
    
    # 2. Website Presence (25 pts)
    web = str(row.get('Website', 'N/A'))
    if web not in ['N/A', 'nan', '']:
        score += 25
        
    # 3. Geo Clarity (25 pts)
    city = str(row.get('City', 'N/A'))
    if city not in ['N/A', 'nan', '']:
        score += 25
        
    # 4. Review Presence (25 pts)
    snippet = str(row.get('Top Reviews Snippet', 'N/A'))
    if snippet not in ['N/A', 'nan', '']:
        score += 25
        
    # 5. Semantic Multiplier (Trust Boost)
    if any(re.search(kw, name) for kw in TRUSTED_NAME_KEYWORDS):
        score = min(100, score + 10)
        
    # 6. Penalty for suspicious names (Deep cut)
    if any(re.search(kw, name) for kw in BAD_NAME_KEYWORDS):
        score -= 60
        
    return max(0, score)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("🚀 Starting Data Trust Refinement...")
    df = pd.read_csv(INPUT_FILE)
    initial_count = len(df)
    
    # SCENARIO 1: SEMANTIC FILTERING
    print("Filtering semantic anomalies...")
    mask = df['Name'].str.lower().apply(lambda x: not any(re.search(kw, str(x)) for kw in BAD_NAME_KEYWORDS))
    # Additionally, if Category implies purely something else (like "Climbing gym")
    # (Assuming Category column exists and has values like 'Amusement park' etc)
    df = df[mask].copy()
    removed_semantic = initial_count - len(df)
    print(f"Removed {removed_semantic} suspicious entities.")
    
    # SCENARIO 2: GEO-ENRICHMENT (FALLBACK)
    print("Enriching missing city data...")
    missing_city_before = df['City'].isna().sum()
    # Use NUTS_NAME as a fallback if City is missing
    df['City'] = df.apply(lambda row: row['NUTS_NAME'] if pd.isna(row['City']) or str(row['City']) == 'nan' else row['City'], axis=1)
    missing_city_after = df['City'].isna().sum()
    print(f"Enriched {missing_city_before - missing_city_after} city entries using NUTS fallback.")
    
    # SCENARIO 4: REFINED TRUST SCORING
    print("Recalculating trust scores...")
    df['data_quality_score'] = df.apply(calculate_refined_score, axis=1)
    
    # Summary
    print("\nTrust Score Distribution:")
    print(df['data_quality_score'].value_counts().sort_index(ascending=False))
    
    avg_score = df['data_quality_score'].mean()
    print(f"\nAverage Data Trust Score: {avg_score:.2f}%")
    
    # Final cleanup of columns if needed
    # Ensure all strings are clean
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Refined dataset saved to {OUTPUT_FILE}")
    print(f"Total records remaining: {len(df)}")

if __name__ == "__main__":
    main()
