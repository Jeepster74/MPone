import pandas as pd
import os
import re
import json

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "premium-dashboard/data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# Sentiment Keywords
CAPEX_KEYWORDS = [
    'asphalt', 'holes', 'bumpy', 'leak', 'leaking', 'cold', 'ventilation', 
    'smoke', 'outdated', 'old karts', 'building', 'maintenance', 'facilities',
    'track surface', 'grip', 'tarmac', 'indoor air'
]

OPEX_KEYWORDS = [
    'staff', 'rude', 'unfriendly', 'service', 'booking', 'double booked', 
    'wait', 'waiting time', 'supervision', 'marshal', 'safety briefing', 
    'organization', 'manager', 'reception', 'attentive'
]

VIBE_KEYWORDS = [
    'toilet', 'restroom', 'dirty', 'hygiene', 'canteen', 'food', 'snack', 
    'atmosphere', 'vibe', 'bar', 'drinks', 'cleaning', 'smell', 'helmets smell'
]

# Sore Loser / Technical Filter
KART_KEYWORDS = ['slow karts', 'kart speed', 'unfair', 'unequal']
TECH_FAILURE_KEYWORDS = ['engine died', 'broke down', 'no brakes', 'stuck', 'failed', 'broken', 'steering']

def analyze_snippet(snippet):
    if not snippet or pd.isna(snippet) or snippet == "N/A":
        return {
            'capex_issues': [],
            'opex_issues': [],
            'vibe_issues': [],
            'tech_failures': []
        }
    
    text = str(snippet).lower()
    
    results = {
        'capex_issues': [kw for kw in CAPEX_KEYWORDS if kw in text],
        'opex_issues': [kw for kw in OPEX_KEYWORDS if kw in text],
        'vibe_issues': [kw for kw in VIBE_KEYWORDS if kw in text],
        'tech_failures': [kw for kw in TECH_FAILURE_KEYWORDS if kw in text]
    }
    
    # "Sore Loser" Filter logic: 
    # If they complain about 'slow karts' but don't mention a technical failure, 
    # we don't count it as a structural CAPEX issue.
    # If they mention 'old karts' + 'slow', that's CAPEX.
    if any(kw in text for kw in KART_KEYWORDS):
        if not results['tech_failures'] and not 'old' in text:
            # Potentially a sore loser, ignore "slow" if it's the only kart complaint
            pass
        else:
            # Valid structural issue or breakdown
            if 'slow' in text and ('old' in text or 'maintenance' in text):
                results['capex_issues'].append('kart performance')
    
    return results

def get_summaries(row):
    snippet = row['Top Reviews Snippet']
    issues = analyze_snippet(snippet)
    
    capex_count = len(issues['capex_issues'])
    opex_count = len(issues['opex_issues'])
    vibe_count = len(issues['vibe_issues'])
    
    # Investment Risk & Rough Diamond Score
    # A rough diamond is: High CAPEX issues, Low Rating, High Population Wealth/Reach
    rating = 0.0
    try:
        rating_str = str(row.get('Average Rating', '0.0'))
        if rating_str not in ["N/A", "nan", ""]:
            rating = float(rating_str)
    except:
        pass
        
    income = 0
    try:
        income = float(row.get('disposable_income_pps', 0))
    except: pass
    
    reach = 0
    try:
        reach = float(row.get('catchment_area_size', 0))
    except: pass

    # Rough Diamond Index (0-100)
    # Factor 1: Structural Issues (Good for investment)
    rd_score = capex_count * 15
    # Factor 2: Low rating (but not 0)
    if 0 < rating < 4.0:
        rd_score += (4.0 - rating) * 20
    # Factor 3: High Wealth
    if income > 25000:
        rd_score += 15
    # Factor 4: High Reach
    if reach > 500:
        rd_score += 10
        
    rd_score = min(100, rd_score)
    
    # Dominant Sentiment
    counts = {
        'Facility/Hardware': capex_count,
        'Management/Service': opex_count,
        'Atmosphere/Hygiene': vibe_count
    }
    
    # Filter 0s and get max
    active = {k: v for k, v in counts.items() if v > 0}
    if not active:
        dominant = "Generally Positive or Neutral"
        problem_type = "None detected"
        risk = "Low - Maintenance mode"
        problem_sum = "No major issues flagged."
    else:
        dom_key = max(active, key=active.get)
        dominant = f"Mostly concerns about {dom_key.lower()}"
        
        # Problem Type
        if capex_count >= opex_count:
            problem_type = "Structural (Building/Track/Fleet)"
            risk = "High CAPEX - Needs renovation or new karts"
            problem_sum = f"Issues detected with: {', '.join(issues['capex_issues'][:3])}"
        else:
            problem_type = "Operational (Service/Management)"
            risk = "Low CAPEX - Management reboot could suffice"
            problem_sum = f"Issues detected with: {', '.join(issues['opex_issues'][:3])}"
            
        if vibe_count > 2:
            problem_sum += f" | Hygiene/Atmosphere concerns: {', '.join(issues['vibe_issues'][:2])}"
            
    return dominant, problem_type, risk, problem_sum, round(rd_score, 1)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    print(f"Analyzing {len(df)} locations...")

    results = df.apply(get_summaries, axis=1, result_type='expand')
    df['dominant_sentiment'] = results[0]
    df['problem_type_summary'] = results[1]
    df['investment_risk_summary'] = results[2]
    df['sentiment_detail_text'] = results[3]
    df['rough_diamond_score'] = results[4]

    # Save results
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Enrichment complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
