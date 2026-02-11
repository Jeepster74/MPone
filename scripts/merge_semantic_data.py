import pandas as pd
import os

# Setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MAIN_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
SEMANTIC_FILE = os.path.join(DATA_DIR, "karting_semantically_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched_v2.csv") # Safer to create v2 first

def merge_data():
    print("Loading datasets...")
    df_main = pd.read_csv(MAIN_FILE)
    df_sem = pd.read_csv(SEMANTIC_FILE)
    
    print(f"Main dataset: {len(df_main)} rows")
    print(f"Semantic dataset: {len(df_sem)} rows")
    
    # Deduplicate semantic data (keep last or first? Last likely most recent if resumed)
    df_sem = df_sem.drop_duplicates(subset=['track_id'], keep='last')
    
    # Merge
    # We want to keep all rows from Main, and update them with Semantic
    merged = df_main.merge(df_sem, on='track_id', how='left', suffixes=('', '_ai'))
    
    # Update logic
    updates_count = 0
    non_karting_count = 0
    
    for index, row in merged.iterrows():
        # Get AI values
        ai_length = row.get('ai_length')
        ai_indoor = row.get('ai_indoor')
        ai_outdoor = row.get('ai_outdoor')
        reasoning = row.get('reasoning', '')
        
        # 1. Update Length if Main is missing or 0, and AI has found it
        current_len = row.get('track_length_m', 0)
        if pd.isna(current_len): current_len = 0
        
        if pd.notna(ai_length) and ai_length > 0:
            # If current is 0 or missing, TAKE IT
            if current_len == 0:
                merged.at[index, 'track_length_m'] = ai_length
                merged.at[index, 'source_length'] = 'AI_Semantic'
                updates_count += 1
            # If current exists but is small (e.g., < 100m often bad OSM data), and AI is bigger?
            # Or trust AI more? 
            # User wanted "The whole file... to be redone". 
            # Let's prioritize AI if confidence is High? 
            # We don't have explicit confidence column in valid JSON in CSV easily without parsing.
            # But we have the value. 
            # Let's say: If AI found a length, use it. (Overwriting OSM potential bad data).
            # Exception: If OSM length is very detailed (e.g. 1234.5), maybe keep? 
            # Safest: Overwrite if different by > 10%?
            # For this pass, let's OVERWRITE if Semantic found something, as it comes from official website text.
            elif abs(current_len - ai_length) > 1: # Diff exists
                 merged.at[index, 'track_length_m'] = ai_length
                 merged.at[index, 'source_length'] = 'AI_Semantic_Overwrite'
                 updates_count += 1

        # 2. Update Indoor/Outdoor
        # Semantic script return True/False/None.
        if pd.notna(ai_indoor):
            merged.at[index, 'is_indoor'] =  bool(ai_indoor)
        
        if pd.notna(ai_outdoor):
             merged.at[index, 'is_outdoor'] = bool(ai_outdoor)
             
        # 3. Flag Non-Karting
        # If reasoning says "Not a karting track" or similar?
        # Or if Length is null and reasoning is "Gym"?
        # We can add a "semantic_notes" column
        merged.at[index, 'semantic_notes'] = reasoning
        
        # Detect "Not a track" based on keywords in reasoning
        if isinstance(reasoning, str):
            negatives = ["not a karting", "gym", "fitness", "holiday apartment", "no information about", "hair salon", "software company"]
            # Be careful not to flag "No information found" as "Not a track" - just unknow.
            # But "Identified as Gym" is useful.
            pass

    # Save
    print(f"Updated {updates_count} track lengths.")
    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_data()
