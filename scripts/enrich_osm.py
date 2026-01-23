import pandas as pd
import osmnx as ox
from shapely.geometry import Point
import time
import os

import geopandas as gpd

# Settings
INPUT_FILE = "../data/karting_enriched.csv"
OUTPUT_FILE = "../data/karting_enriched.csv"
TEST_LIMIT = None # Set to None for full run

def get_osm_data(lat, lon):
    """
    Fetches building footprint and B2B density from OSM using optimized queries.
    """
    point = (lat, lon)
    res = {
        'building_sqm': 0,
        'b2b_density': 0
    }
    
    try:
        # 1. Building Footprint (Small radius = Fast)
        try:
            footprint_tags = {'building': True, 'leisure': 'sports_centre'}
            footprint_features = ox.features_from_point(point, tags=footprint_tags, dist=300)
            
            p_geom = Point(lon, lat)
            polygons = footprint_features[footprint_features.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            
            if not polygons.empty:
                containing = polygons[polygons.intersects(p_geom)]
                if not containing.empty:
                    target = containing.head(1)
                else:
                    polygons = polygons.copy()
                    polygons['dist'] = polygons.geometry.distance(p_geom)
                    target = polygons.nsmallest(1, 'dist')
                
                target_proj = ox.projection.project_gdf(target)
                res['building_sqm'] = round(target_proj.geometry.area.iloc[0], 2)
        except:
            pass # No footprint found locally

        # 2. B2B Density (Large radius but filtered tags = Fast)
        try:
            density_tags = {
                'office': True,
                'industrial': True,
                'landuse': ['industrial', 'commercial', 'office']
            }
            # We explicitly do NOT include building=True here to avoid downloading every house in 2km
            density_features = ox.features_from_point(point, tags=density_tags, dist=2000)
            if not density_features.empty:
                res['b2b_density'] = len(density_features)
        except:
            pass
            
    except Exception as e:
        print(f"OSM lookup error at {lat}, {lon}: {e}")
        
    return res

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Initialize columns if not present
    if 'building_sqm' not in df.columns:
        df['building_sqm'] = "N/A"
    if 'b2b_density' not in df.columns:
        df['b2b_density'] = "N/A"

    # Filter for rows that need processing
    mask = (df['building_sqm'] == "N/A") | (df['building_sqm'].isna())
    to_process = df[mask]
    
    if TEST_LIMIT:
        to_process = to_process.head(TEST_LIMIT)
        
    print(f"Processing {len(to_process)} locations...")

    processed_count = 0
    for index, row in to_process.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        if pd.isna(lat) or pd.isna(lon):
            continue
            
        print(f"[{processed_count + 1}/{len(to_process)}] Processing: {row['Name']}...")
        osm_res = get_osm_data(lat, lon)
        
        df.at[index, 'building_sqm'] = osm_res['building_sqm']
        df.at[index, 'b2b_density'] = osm_res['b2b_density']
        
        processed_count += 1
        
        if processed_count % 10 == 0:
            df.to_csv(OUTPUT_FILE, index=False)
            
        time.sleep(1) # Rate limit protection

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nFinished batch of {processed_count}. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    # Configure osmnx to use cache to speed up repeated queries
    ox.settings.use_cache = True
    ox.settings.log_console = False
    main()
