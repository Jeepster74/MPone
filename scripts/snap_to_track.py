import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
import os

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
SNAP_RADIUS_M = 200 # Radius in meters to consider locations as potentially the same

def haversine(lat1, lon1, lat2, lon2):
    # Degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km * 1000 # returns meters

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    if 'data_quality_score' not in df.columns:
        # Simple quality heuristic if score is missing
        df['data_quality_score'] = df.apply(lambda r: 10 if pd.notna(r['Hero Image URL']) and r['Hero Image URL'] != 'N/A' else 5, axis=1)

    initial_count = len(df)
    print(f"Analyzing {initial_count} records for spatial proximity...")

    # Convert lat/lon to radians for the tree
    coords = np.deg2rad(df[['Latitude', 'Longitude']].values)
    tree = cKDTree(coords)
    
    # Radians for the search radius (approximate)
    # Earth's radius in meters is ~6,371,000
    radius_rad = SNAP_RADIUS_M / 6371000.0
    
    to_drop = set()
    snapped_count = 0
    
    processed = set()
    
    for i in range(len(df)):
        if i in processed or i in to_drop:
            continue
            
        # Find points within radius
        indices = tree.query_ball_point(coords[i], radius_rad)
        
        if len(indices) > 1:
            # We found potential spatial duplicates
            group = df.iloc[indices]
            # Identify the "best" record based on data quality score
            best_idx_in_group = group['data_quality_score'].idxmax()
            best_row = df.loc[best_idx_in_group]
            
            for idx in indices:
                actual_idx = df.index[idx]
                if actual_idx == best_idx_in_group:
                    continue
                
                # Verify they are indeed likely the same (e.g. similar category or name)
                # For now, if they are within 200m in this dataset, they are likely duplicates 
                # given our previous deduplication.
                print(f" - Snap: {df.loc[actual_idx, 'Name']} -> {best_row['Name']} (Dist: {haversine(df.loc[actual_idx, 'Latitude'], df.loc[actual_idx, 'Longitude'], best_row['Latitude'], best_row['Longitude']):.1f}m)")
                to_drop.add(actual_idx)
                snapped_count += 1
                processed.add(actual_idx)
                
        processed.add(i)

    if not to_drop:
        print("No spatial duplicates found.")
    else:
        df_final = df.drop(index=list(to_drop))
        print(f"\nSnapped {snapped_count} spatial duplicates.")
        print(f"Final count: {len(df_final)}")
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"Snapped dataset saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
