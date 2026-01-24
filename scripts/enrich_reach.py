import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, mapping
import openrouteservice
from openrouteservice import isochrones
import os
import json
import time
import asyncio

# Settings
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
GEOJSON_FILE = os.path.join(DATA_DIR, "karting_shapes.geojson")

# Replace with your API key
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjFjZDZmZDJjZWVkMTQ0NGZiNzg0N2U5Mzg4OTQzNWU1IiwiaCI6Im11cm11cjY0In0="

def get_isochrone(client, lat, lon, range_min=30):
    """
    Fetches a 30-minute drive-time isochrone for a given point.
    """
    # ORS takes coordinates as [lon, lat]
    coords = [[lon, lat]]
    
    try:
        # profile='driving-car', range_type='time', range=[range_min * 60] (in seconds)
        iso = client.isochrones(
            locations=coords,
            profile='driving-car',
            range=[range_min * 60],
            validate=False
        )
        return iso
    except Exception as e:
        print(f"Error fetching isochrone for {lat}, {lon}: {e}")
        return None

def calculate_area_km2(geojson_iso):
    """
    Calculates the area of the isochrone in square kilometers.
    """
    try:
        # Load the feature into a GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_iso['features'])
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Project to LAEA Europe (Equal Area) or fallback to World Cylindrical Equal Area
        try:
            gdf_proj = gdf.to_crs(epsg=3035)
        except:
            # Fallback to Mollweide (ESRI:54009) or similar if outside Europe
            gdf_proj = gdf.to_crs("+proj=moll +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
        
        # Area in sqm -> convert to sq km
        area_km2 = gdf_proj.geometry.area.sum() / 1_000_000
        return round(area_km2, 2)
    except Exception as e:
        print(f"Error calculating area: {e}")
        return 0

def safe_save(results_dict, output_file, geojson_features, geojson_file):
    """
    Reloads the CSV from disk, merges new results, and saves.
    This prevents overwriting columns added by other scripts (like classify_facility.py).
    """
    try:
        # 1. Reload the current state of the file
        current_df = pd.read_csv(output_file)
        
        # 2. Update only the catchment_area_size for processed IDs
        if 'catchment_area_size' not in current_df.columns:
            current_df['catchment_area_size'] = "N/A"
            
        for track_id, area in results_dict.items():
            current_df.loc[current_df['track_id'] == track_id, 'catchment_area_size'] = area
            
        # 3. Save CSV
        current_df.to_csv(output_file, index=False)
        
        # 4. Save GeoJSON
        with open(geojson_file, 'w') as f:
            json.dump({"type": "FeatureCollection", "features": geojson_features}, f)
            
        print(f"--- Concurrency-Safe Save Complete ({len(results_dict)} items merged) ---")
    except Exception as e:
        print(f"Error during safe save: {e}")

async def main():
    if API_KEY == "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjFjZDZmZDJjZWVkMTQ0NGZiNzg0N2U5Mzg4OTQzNWU1IiwiaCI6Im11cm11cjY0In0=":
        # Verification: Correct key is present
        pass

    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("Loading track data...")
    df = pd.read_csv(INPUT_FILE)
    keywords = {} # Not used here but keep logic clean

    # Initialize client
    client = openrouteservice.Client(key=API_KEY)
    
    # Load existing GeoJSON if exists for resumability
    all_features = []
    processed_ids = set()
    if os.path.exists(GEOJSON_FILE):
        try:
            with open(GEOJSON_FILE, 'r') as f:
                existing_data = json.load(f)
                all_features = existing_data['features']
                processed_ids = {f['properties']['track_id'] for f in all_features}
                print(f"Resuming from existing GeoJSON. {len(processed_ids)} tracks already processed.")
        except:
            print("GeoJSON corrupted, starting fresh.")

    # Filter for rows that need processing
    to_process = df[(df['catchment_area_size'] == "N/A") | (df['catchment_area_size'].isna()) | (df['catchment_area_size'] == 0)]
    print(f"Total locations needing enrichment: {len(to_process)}")

    success_count = 0
    batch_results = {} # track_id -> area
    quota_reached = False
    
    for index, row in to_process.iterrows():
        track_id = int(row['track_id'])
        if track_id in processed_ids:
            continue
            
        lat, lon = row['Latitude'], row['Longitude']
        print(f"[{success_count+1}] Fetching isochrone for: {row['Name']} (ID: {track_id})...")
        
        try:
            iso_res = get_isochrone(client, lat, lon)
            if iso_res:
                # Add track_id to properties for linking
                for feature in iso_res['features']:
                    feature['properties']['track_id'] = track_id
                    all_features.append(feature)
                
                # Calculate area
                area = calculate_area_km2(iso_res)
                batch_results[track_id] = area
                success_count += 1
                
                # Save progress every 10
                if success_count % 10 == 0:
                    safe_save(batch_results, OUTPUT_FILE, all_features, GEOJSON_FILE)
                    # Don't clear batch_results, keep them for final save or clear if merge is cumulative
                
                # Rate limit protection
                time.sleep(4) 
            else:
                print(f"Failed to fetch isochrone for ID: {track_id}")
        except Exception as e:
            if "OverQueryLimit" in str(e) or "429" in str(e):
                print("\n!!! DAILY QUOTA REACHED !!!")
                quota_reached = True
                break
            else:
                print(f"Unexpected error at ID {track_id}: {e}")

    # Final Save
    safe_save(batch_results, OUTPUT_FILE, all_features, GEOJSON_FILE)
        
    if quota_reached:
        print("\nProcess paused. You can resume tomorrow.")
    else:
        print(f"\nFinished batch. Total processed: {success_count}")

if __name__ == "__main__":
    asyncio.run(main())
