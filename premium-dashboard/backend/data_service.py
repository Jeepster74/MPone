import pandas as pd
import json
import os
from typing import List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Inside Docker, data is at /app/data. In local dev, it's at ../data
DATA_DIR = "/app/data" if os.path.exists("/app/data") else os.path.join(ROOT_DIR, "..", "data")
CSV_PATH = os.path.join(DATA_DIR, "karting_enriched.csv")
GEOJSON_PATH = os.path.join(DATA_DIR, "karting_shapes.geojson")
WISHLIST_PATH = os.path.join(DATA_DIR, "wishlist.json")

def get_tracks_data():
    """
    Safely reads the enriched CSV and robustly sanitizes for JSON.
    Calculates Data Quality Index (DQI) if not present.
    """
    import math
    
    def sanitize(v, key=None):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        # Explicitly ensure boolean flags for frontend filtering
        if key in ['is_indoor', 'is_outdoor', 'is_sim']:
            if str(v).lower() in ['true', '1', '1.0', 'yes']: return True
            if str(v).lower() in ['false', '0', '0.0', 'no', 'nan', 'none']: return False
            return bool(v)
        return v

    def calculate_dq_score(row):
        """
        Calculates a Data Quality Index (0-100) based on field completeness.
        """
        essential_fields = ['Name', 'Latitude', 'Longitude', 'Country', 'Category']
        bonus_fields = ['Review Velocity (12m)', 'Hero Image URL', 'Top Reviews Snippet']
        
        score = 0
        max_score = len(essential_fields) * 15 + len(bonus_fields) * 8
        
        for field in essential_fields:
            val = row.get(field)
            if val and str(val).strip() and not (isinstance(val, float) and math.isnan(val)):
                # Penalty for unrecovered names
                if field == 'Name' and str(val).startswith('track_'):
                    score += 5
                else:
                    score += 15
        
        for field in bonus_fields:
            val = row.get(field)
            if val and str(val).strip() and not (isinstance(val, float) and math.isnan(val)):
                score += 8
                
        return min(100, round((score / max_score) * 100, 1))

    try:
        if not os.path.exists(CSV_PATH):
            print(f"CRITICAL: CSV not found at {os.path.abspath(CSV_PATH)}")
            return []
            
        df = pd.read_csv(CSV_PATH)
        print(f"SUCCESS: Loaded {len(df)} tracks from {CSV_PATH}")
        
        # Ensure data_quality_score exists
        if 'data_quality_score' not in df.columns:
            df['data_quality_score'] = df.apply(calculate_dq_score, axis=1)
        
        # Consolidation and Key Cleanup
        clean_data = []
        for _, row in df.iterrows():
            record = row.to_dict()
            
            # 1. Consolidated Track Length
            # Prioritize Website scraping, then OSM
            web_len = sanitize(record.get('website_track_length_m'))
            osm_len = sanitize(record.get('track_length_m'))
            
            # Filter out -1 (placeholder for failed scrape)
            best_len = 0
            if isinstance(web_len, (int, float)) and web_len > 0:
                best_len = web_len
            elif isinstance(osm_len, (int, float)) and osm_len > 0:
                best_len = osm_len
            
            record['consolidated_track_length'] = best_len
            
            # 2. Key Cleanup for Frontend
            # Mapping CSV names to what Frontend expects
            key_map = {
                'Review Velocity (12m)': 'Review Velocity',
                'Owner Activity': 'Owner Responds'
            }
            
            sanitized_record = {}
            for k, v in record.items():
                target_k = key_map.get(k, k)
                sanitized_record[target_k] = sanitize(v, target_k)
            
            clean_data.append(sanitized_record)
            
        return clean_data
    except Exception as e:
        import traceback
        print(f"ERROR: Failed to load tracks CSV: {e}")
        traceback.print_exc()
        return []

_cached_geojson = None
_geojson_mtime = 0

def get_geojson_data():
    """
    Reads the shapes file and caches it. 
    Invalidates cache if the file on disk has been updated (mtime check).
    """
    global _cached_geojson, _geojson_mtime
    
    try:
        if not os.path.exists(GEOJSON_PATH):
            print(f"WARNING: GeoJSON not found at {GEOJSON_PATH}")
            return {"type": "FeatureCollection", "features": []}
            
        current_mtime = os.path.getmtime(GEOJSON_PATH)
        
        # Return cache only if file hasn't changed
        if _cached_geojson is not None and current_mtime <= _geojson_mtime:
            return _cached_geojson
            
        print(f"LOADING GEOJSON: Loading {os.path.getsize(GEOJSON_PATH)/1024/1024:.2f} MB shapes file...")
        with open(GEOJSON_PATH, 'r') as f:
            _cached_geojson = json.load(f)
            _geojson_mtime = current_mtime
            print(f"SUCCESS: GeoJSON loaded cached ({len(_cached_geojson.get('features', []))} features)")
            return _cached_geojson
            
    except MemoryError:
        print("CRITICAL: Out of memory while loading GeoJSON!")
        return {"type": "FeatureCollection", "features": []}
    except Exception as e:
        print(f"Error reading GeoJSON: {e}")
        import traceback
        traceback.print_exc()
        return {"type": "FeatureCollection", "features": []}

def load_wishlist(username: str):
    if not os.path.exists(WISHLIST_PATH):
        return []
    try:
        with open(WISHLIST_PATH, 'r') as f:
            data = json.load(f)
            return data.get(username, [])
    except:
        return []

def update_wishlist(username: str, track_id: int, action: str):
    data = {}
    if os.path.exists(WISHLIST_PATH):
        try:
            with open(WISHLIST_PATH, 'r') as f:
                data = json.load(f)
        except:
            pass
            
    user_list = data.get(username, [])
    if action == "add":
        if track_id not in user_list:
            user_list.append(track_id)
    elif action == "remove":
        if track_id in user_list:
            user_list.remove(track_id)
            
    data[username] = user_list
    with open(WISHLIST_PATH, 'w') as f:
        json.dump(data, f)
    return user_list
