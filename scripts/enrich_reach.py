import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, mapping
import openrouteservice
from openrouteservice import isochrones
import os
import json
import time

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

def enrich_reach():
    if API_KEY == "YOUR_ORS_API_KEY_HERE":
        print("Error: Please provide a valid OpenRouteService API key.")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("Loading track data...")
    df = pd.read_csv(INPUT_FILE)
    
    if 'catchment_area_size' not in df.columns:
        df['catchment_area_size'] = "N/A"

    # Initialize client
    client = openrouteservice.Client(key=API_KEY)
    
    # Load existing GeoJSON if exists for resumability
    all_features = []
    processed_ids = set()
    if os.path.exists(GEOJSON_FILE):
        with open(GEOJSON_FILE, 'r') as f:
            existing_data = json.load(f)
            all_features = existing_data['features']
            processed_ids = {f['properties']['track_id'] for f in all_features}
            print(f"Resuming from existing GeoJSON. {len(processed_ids)} tracks already processed.")

    # Filter for rows that need processing
    to_process = df[(df['catchment_area_size'] == "N/A") | (df['catchment_area_size'].isna())]
    print(f"Total locations needing enrichment: {len(to_process)}")

    count = 0
    success_count = 0
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
                df.at[index, 'catchment_area_size'] = area
                success_count += 1
                
                # Save progress every 10
                if success_count % 10 == 0:
                    df.to_csv(OUTPUT_FILE, index=False)
                    with open(GEOJSON_FILE, 'w') as f:
                        json.dump({"type": "FeatureCollection", "features": all_features}, f)
                    print(f"--- Progress Saved ({success_count} processed) ---")
                
                # Rate limit protection (ORS free: 20/min = 1 every 3s). Use 4s to be safe.
                time.sleep(4) 
            else:
                print(f"Failed to fetch isochrone for ID: {track_id}")
        except Exception as e:
            if "OverQueryLimit" in str(e) or "429" in str(e):
                print("\n!!! DAILY QUOTA REACHED or RATE LIMIT EXCEEDED !!!")
                print("Stopping script to prevent further errors.")
                quota_reached = True
                break
            else:
                print(f"Unexpected error at ID {track_id}: {e}")

    # Final Save
    df.to_csv(OUTPUT_FILE, index=False)
    with open(GEOJSON_FILE, 'w') as f:
        json.dump({"type": "FeatureCollection", "features": all_features}, f)
        
    if quota_reached:
        print("\nProcess paused due to API limits. You can resume tomorrow.")
    else:
        print(f"\nFinished batch. Total processed this session: {success_count}")

if __name__ == "__main__":
    enrich_reach()
