import pandas as pd
import numpy as np
import os
import math

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

def calculate_dqi(row):
    """Simple DQI for sorting/merging priority"""
    essential = ['Name', 'Latitude', 'Longitude', 'Country', 'Category']
    bonus = ['Review Velocity (12m)', 'Hero Image URL', 'Top Reviews Snippet']
    
    score = 0
    for f in essential:
        val = row.get(f)
        if val and str(val).lower() != 'nan':
            score += 15
            
    for f in bonus:
        val = row.get(f)
        if val and str(val).lower() not in ['nan', 'n/a', 'failed', '']:
            score += 8
            
    return score

def consolidate_group(group):
    """
    Consolidates a group of duplicate records into a single master record.
    """
    # Sort by DQI to find the best candidate for Master
    group = group.copy()
    group['temp_dqi'] = group.apply(calculate_dqi, axis=1)
    group = group.sort_values('temp_dqi', ascending=False)
    
    master = group.iloc[0].copy()
    
    # Merge rich metadata from children if Master is missing it
    fields_to_fill = ['Hero Image URL', 'Top Reviews Snippet', 'Official Website', 'Maps URL', 'City']
    for field in fields_to_fill:
        if str(master.get(field, 'N/A')) in ['N/A', 'nan', 'FAILED', '']:
            # Find first child that has this field
            for _, child in group.iterrows():
                val = child.get(field)
                if val and str(val) not in ['N/A', 'nan', 'FAILED', '']:
                    master[field] = val
                    break
                    
    # Sum or max for numeric metrics
    if 'Review Velocity (12m)' in master:
        try:
            velocities = pd.to_numeric(group['Review Velocity (12m)'], errors='coerce').fillna(0)
            master['Review Velocity (12m)'] = velocities.max()
        except:
            pass

    return master

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    initial_count = len(df)
    print(f"Initial records: {initial_count}")

    # 1. Clean up "Silverstone" specifically if it's a known artifact
    # The user mentioned Silverstone has 600 records.
    
    # 2. Geometric Clustering (Simple approach: round coordinates to 3 decimals ~110m)
    # This groups points that are very close to each other.
    df['lat_cluster'] = df['Latitude'].round(3)
    df['lon_cluster'] = df['Longitude'].round(3)
    
    # 3. Name-based grouping (Fuzzy-ish)
    # Simplify names for grouping
    df['name_clean'] = df['Name'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True).fillna('unknown')
    
    # Define a group as same location (rounded) AND similar name
    # OR same exact name
    print("Deduplicating...")
    
    # Strategy: Group by name first, if name is identical, they are the same.
    # If name is different but coordinates are extremely close, we might want to flag them.
    
    # First pass: Exact Name + Country
    deduped = []
    groups = df.groupby(['Name', 'Country'])
    
    for _, group in groups:
        if len(group) > 1:
            deduped.append(consolidate_group(group))
        else:
            deduped.append(group.iloc[0])
            
    df_new = pd.DataFrame(deduped)
    
    # Second pass: Geometric proximity for records with different names but same spot
    # Round to 4 decimals (~11m) 
    df_new['lat_rnd'] = df_new['Latitude'].round(4)
    df_new['lon_rnd'] = df_new['Longitude'].round(4)
    
    final_deduped = []
    geo_groups = df_new.groupby(['lat_rnd', 'lon_rnd'])
    for _, group in geo_groups:
        if len(group) > 1:
            final_deduped.append(consolidate_group(group))
        else:
            final_deduped.append(group.iloc[0])

    df_final = pd.DataFrame(final_deduped)
    
    # Clean up temp columns
    cols_to_drop = ['temp_dqi', 'lat_cluster', 'lon_cluster', 'name_clean', 'lat_rnd', 'lon_rnd']
    df_final = df_final.drop(columns=[c for c in cols_to_drop if c in df_final.columns])

    print(f"Final records: {len(df_final)}")
    print(f"Removed {initial_count - len(df_final)} duplicates.")

    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"Cleaned dataset saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
