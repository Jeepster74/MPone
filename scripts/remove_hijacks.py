import pandas as pd
import os

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# Known brands that are geography-locked
# If these appear in other countries, they are likely hijacks/errors
BRAND_LOCKS = {
    'Silverstone': ['United Kingdom'],
    'Buckmore Park': ['United Kingdom'],
    'Daytona': ['United Kingdom'],
    'TeamSport': ['United Kingdom'],
    'Karting Eupen': ['Belgium'],
    'Michael Schumacher Kart': ['Germany'],
    'Speedworld': ['Austria'],
    'Karting des Fagnes': ['Belgium'],
    'Circuit de Spa-Francorchamps': ['Belgium'],
    'South Garda': ['Italy'],
    'Lonato': ['Italy']
}

def is_hijack(row):
    name = str(row['Name']).lower()
    country = str(row['Country'])
    
    for brand, allowed_countries in BRAND_LOCKS.items():
        if brand.lower() in name:
            if country not in allowed_countries:
                return True, f"Brand '{brand}' locked to {allowed_countries}, found in {country}"
                
    return False, ""

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    initial_count = len(df)
    
    print(f"Analyzing {initial_count} records for hijacks...")
    
    hijacks = []
    for idx, row in df.iterrows():
        check, reason = is_hijack(row)
        if check:
            hijacks.append((idx, row['Name'], row['Country'], reason))
            
    if not hijacks:
        print("No hijacks found.")
        return
        
    print(f"Found {len(hijacks)} hijacks:")
    for _, name, country, reason in hijacks:
        print(f" - REMOVE: {name} ({country}) | {reason}")
        
    # Remove hijacks
    indices_to_drop = [h[0] for h in hijacks]
    df_clean = df.drop(indices_to_drop)
    
    print(f"\nRemoved {len(hijacks)} records.")
    print(f"Final count: {len(df_clean)}")
    
    df_clean.to_csv(OUTPUT_FILE, index=False)
    print(f"Cleaned dataset saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
