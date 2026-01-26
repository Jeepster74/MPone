import pandas as pd
import json
import os
from typing import List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT_DIR, "data", "karting_enriched.csv")
GEOJSON_PATH = os.path.join(ROOT_DIR, "data", "karting_shapes.geojson")
WISHLIST_PATH = os.path.join(ROOT_DIR, "data", "wishlist.json")

def get_tracks_data():
    """
    Safely reads the enriched CSV and robustly sanitizes for JSON.
    """
    import math
    
    def sanitize(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    try:
        if not os.path.exists(CSV_PATH):
            return []
            
        df = pd.read_csv(CSV_PATH)
        raw_data = df.to_dict(orient="records")
        
        # Manually sanitize every field to ensure JSON compliance
        clean_data = [
            {k: sanitize(v) for k, v in record.items()}
            for record in raw_data
        ]
        
        return clean_data
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

_cached_geojson = None

def get_geojson_data():
    """
    Safely reads and caches the shapes file to avoid repeated disk I/O and parsing.
    """
    global _cached_geojson
    if _cached_geojson is not None:
        return _cached_geojson
        
    try:
        if os.path.exists(GEOJSON_PATH):
            with open(GEOJSON_PATH, 'r') as f:
                _cached_geojson = json.load(f)
                return _cached_geojson
        return {"type": "FeatureCollection", "features": []}
    except Exception as e:
        print(f"Error reading GeoJSON: {e}")
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
