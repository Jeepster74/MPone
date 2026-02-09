"""
Gemini-Powered Review Analysis Script
Analyzes Google reviews using Gemini API to generate structured insights.
"""
import pandas as pd
import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai

# Setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# Load API key
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=GEMINI_API_KEY)
# Use gemini-2.5-flash (newer model, may have separate quota)
model = genai.GenerativeModel('gemini-2.5-flash')

# Rate limiting: Paid tier allows 60+ req/min, but we add small delay to be safe
RATE_LIMIT_DELAY = 1

PROMPT_TEMPLATE = """You are an M&A analyst screening go-kart facilities for acquisition targets.

TASK: Analyze these customer reviews and extract investment-relevant signals.

REVIEWS:
{reviews}

---

ANALYSIS FRAMEWORK:

1. **ASSET CONDITION** (physical infrastructure)
   - Look for: track surface, kart quality, ventilation, building issues, safety equipment
   - Signal words: "bumpy", "old karts", "cold", "smoke", "new track", "modern"

2. **OPERATIONS** (management & service)  
   - Look for: staff behavior, wait times, booking issues, safety procedures
   - Signal words: "rude", "friendly", "organized", "chaotic", "professional"

3. **MARKET FIT** (customer satisfaction & positioning)
   - Look for: value perception, repeat visit intent, competitive comparisons
   - Signal words: "worth it", "overpriced", "fun", "boring", "best in area"

---

OUTPUT FORMAT (respond with ONLY this JSON):

{{
  "asset": "{{verdict}}: {{one-liner max 10 words}}",
  "ops": "{{verdict}}: {{one-liner max 10 words}}",
  "market": "{{verdict}}: {{one-liner max 10 words}}",
  "sentiment": "positive|mixed|negative",
  "confidence": "high|medium|low"
}}

Where {{verdict}} is one of: "Strong", "Adequate", "Weak", "Needs Investment", "Data Gap"

---

EXAMPLE OUTPUT:
{{
  "asset": "Weak: Track surface worn, karts described as old and slow",
  "ops": "Strong: Staff praised for friendliness, well-organized events",
  "market": "Adequate: Good value but long wait times on weekends",
  "sentiment": "mixed",
  "confidence": "medium"
}}"""


def analyze_with_gemini(reviews_text: str) -> dict:
    """Send reviews to Gemini and get structured insights."""
    if not reviews_text or reviews_text == "N/A" or len(reviews_text) < 20:
        return {
            "insights": ["Data Gap: Insufficient review data for analysis"],
            "sentiment": "neutral",
            "confidence": "low"
        }
    
    try:
        prompt = PROMPT_TEMPLATE.format(reviews=reviews_text[:4000])  # Limit token usage
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        text = response.text.strip()
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(text)
        
        # Convert new format (asset/ops/market) to insights array
        insights = []
        if "asset" in result:
            insights.append(f"Asset: {result['asset']}")
        if "ops" in result:
            insights.append(f"Ops: {result['ops']}")
        if "market" in result:
            insights.append(f"Market: {result['market']}")
        
        # Fallback to old format if present
        if not insights and "insights" in result:
            insights = result.get("insights", [])[:3]
        
        return {
            "insights": insights if insights else ["Analysis parsing failed"],
            "sentiment": result.get("sentiment", "neutral"),
            "confidence": result.get("confidence", "low")
        }
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {"insights": ["Analysis parsing failed"], "sentiment": "neutral", "confidence": "low"}
    except Exception as e:
        print(f"Gemini API error: {e}")
        return {"insights": ["API analysis unavailable"], "sentiment": "neutral", "confidence": "low"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Analyze reviews with Gemini AI')
    parser.add_argument('--force', action='store_true', help='Re-analyze all locations (ignore existing insights)')
    parser.add_argument('--batch', type=int, default=1000, help='Max locations to process')
    args = parser.parse_args()
    
    print("Loading data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Initialize new columns
    if 'ai_insights' not in df.columns:
        df['ai_insights'] = None
    if 'ai_sentiment' not in df.columns:
        df['ai_sentiment'] = None
    if 'ai_confidence' not in df.columns:
        df['ai_confidence'] = None
    if 'review_count_12m' not in df.columns:
        df['review_count_12m'] = 0
    
    # Process locations that need analysis
    # Use Top Reviews Snippet as input (already contains translated reviews)
    if args.force:
        # Re-analyze all locations with valid snippets
        to_process = df[df['Top Reviews Snippet'].notna() & (df['Top Reviews Snippet'].astype(str).str.len() > 10) & (df['Top Reviews Snippet'].astype(str) != 'nan')]
        print(f"FORCE MODE: Re-analyzing {len(to_process)} locations with review data...")
    else:
        to_process = df[df['ai_insights'].isna() | (df['ai_insights'] == '')]
    
    # Apply batch limit
    to_process = to_process.head(args.batch)
    
    print(f"Analyzing {len(to_process)} locations with Gemini...")
    
    processed = 0
    for index, row in to_process.iterrows():
        snippet = str(row.get('Top Reviews Snippet', 'N/A'))
        velocity = row.get('Review Velocity (12m)', 0)
        
        # Convert velocity to int safely
        try:
            velocity = int(velocity) if pd.notna(velocity) and velocity != 'N/A' and velocity != 'FAILED' else 0
        except:
            velocity = 0
        
        result = analyze_with_gemini(snippet)
        
        df.at[index, 'ai_insights'] = json.dumps(result['insights'])
        df.at[index, 'ai_sentiment'] = result['sentiment']
        df.at[index, 'ai_confidence'] = result['confidence']
        df.at[index, 'review_count_12m'] = velocity
        
        processed += 1
        if processed % 10 == 0:
            print(f"Processed {processed}/{len(to_process)}...")
            df.to_csv(OUTPUT_FILE, index=False)
        
        time.sleep(RATE_LIMIT_DELAY)  # Respect API limits
    
    # Final save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Complete! Analyzed {processed} locations. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
