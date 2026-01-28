import pandas as pd
import osmnx as ox
from shapely.geometry import Point, LineString, MultiLineString
import time
import os
import sys

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
TEST_LIMIT = None # Set to None for full run

def get_track_length(lat, lon):
    """
    Fetches track length from OSM using leisures=track and sport=karting.
    """
    point = (lat, lon)
    try:
        # Search for leisure=track or sport=karting or highway=raceway
        tags = {
            'leisure': 'track',
            'sport': 'karting',
            'highway': 'raceway'
        }
        
        # We search in a 500m radius to catch the track geometry
        features = ox.features_from_point(point, tags=tags, dist=500)
        
        if features.empty:
            return 0
        
        # Filter for LineString or MultiLineString (actual track paths)
        # or Polygons (which we can get the perimeter of)
        tracks = features[features.geometry.type.isin(['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'])]
        
        if tracks.empty:
            return 0
            
        # Project to local CRS for accurate measurement
        tracks_proj = ox.projection.project_gdf(tracks)
        
        lengths = []
        for idx, row in tracks_proj.iterrows():
            geom = row.geometry
            if geom.type in ['LineString', 'MultiLineString']:
                lengths.append(geom.length)
            elif geom.type in ['Polygon', 'MultiPolygon']:
                # For polygons, the "length" is the perimeter
                lengths.append(geom.boundary.length)
        
        if not lengths:
            return 0
            
        # Usually the longest one in the vicinity is the main track
        # but we also sum them if they are parts of the same facility
        # However, for karting, often a single polygon/line represents the track.
        # We'll take the max to avoid double-counting if there are many sub-segments
        return round(max(lengths), 0)
        
    except Exception as e:
        # Silent fail as many locations won't have OSM track data
        return 0

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Initialize column if not present
    if 'track_length_m' not in df.columns:
        df['track_length_m'] = 0

    # Filter for rows that need processing (length is 0 or NaN)
    mask = (df['track_length_m'] == 0) | (df['track_length_m'].isna())
    to_process = df[mask]
    
    if TEST_LIMIT:
        to_process = to_process.head(TEST_LIMIT)
        
    print(f"Processing {len(to_process)} locations for track length...")

    processed_count = 0
    for index, row in to_process.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        if pd.isna(lat) or pd.isna(lon):
            continue
            
        print(f"[{processed_count + 1}/{len(to_process)}] Processing: {row['Name']}...")
        length = get_track_length(lat, lon)
        
        if length > 0:
            print(f"   --> Found length: {length}m")
            df.at[index, 'track_length_m'] = length
        
        processed_count += 1
        
        if processed_count % 10 == 0:
            df.to_csv(OUTPUT_FILE, index=False)
            
        time.sleep(0.5) # Rate limit protection

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nFinished batch of {processed_count}. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    ox.settings.use_cache = True
    ox.settings.log_console = False
    main()
