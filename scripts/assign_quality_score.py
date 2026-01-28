import pandas as pd
import os

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

def calculate_quality_score(row):
    score = 0
    
    # 1. Name Presence (20%)
    name = str(row.get('Name', 'nan')).lower()
    if name not in ['nan', 'n/a', 'karting', 'sim']:
        score += 20
    
    # 2. Hero Image (20%)
    img = str(row.get('Hero Image URL', 'N/A'))
    if img not in ['N/A', 'nan', 'FAILED', '']:
        score += 20
        
    # 3. Reviews/Sentiment (20%)
    snippet = str(row.get('Top Reviews Snippet', 'N/A'))
    if snippet not in ['N/A', 'nan', '']:
        score += 20
        
    # 4. Wealth Data (20%)
    wealth = row.get('disposable_income_pps', 0)
    if pd.notna(wealth) and wealth > 0:
        score += 20
        
    # 5. Catchment Area (20%)
    catchment = str(row.get('catchment_area_size', 'N/A'))
    if catchment not in ['N/A', 'nan', '0', '0.0'] and pd.notna(catchment):
        # Additional check for numeric values > 0
        try:
            if float(catchment) > 0:
                score += 20
        except:
            pass
            
    return score

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("Calculating quality scores...")
    df = pd.read_csv(INPUT_FILE)
    
    df['data_quality_score'] = df.apply(calculate_quality_score, axis=1)
    
    # Summary stats
    print("\nQuality Score Distribution:")
    print(df['data_quality_score'].value_counts().sort_index(ascending=False))
    
    avg_score = df['data_quality_score'].mean()
    print(f"\nAverage Data Quality Score: {avg_score:.2f}%")
    
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Scores saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
