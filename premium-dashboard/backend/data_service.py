import pandas as pd
import json
import os
from typing import List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(ROOT_DIR, "data", "karting_enriched.csv")
GEOJSON_PATH = os.path.join(ROOT_DIR, "data", "karting_shapes.geojson")
WISHLIST_PATH = os.path.join(ROOT_DIR, "data", "wishlist.json")

def get_tracks_data():
    """
    Safely reads the enriched CSV in read-only mode.
    """
    try:
        # Use low_memory=False to ensure stable data types
        # Open in read-only mode explicitly
        with open(CSV_PATH, 'r') as f:
            df = pd.read_csv(f)
            
        # Fill NaNs for JSON stability
        df = df.fillna({
            "City": "N/A",
            "Website": "N/A",
            "Top Reviews Snippet": "No current reviews",
            "catchment_area_size": 0
        })
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

def get_geojson_data():
    """
    Safely reads the shapes file.
    """
    try:
        if os.path.exists(GEOJSON_PATH):
            with open(GEOJSON_PATH, 'r') as f:
                return json.load(f)
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
