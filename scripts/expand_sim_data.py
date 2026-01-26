import overpy
import pandas as pd
import time
import ssl
import os
from math import cos, sqrt, pi

# Bypass SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

def calculate_distance(lat1, lon1, lat2, lon2):
    # Rough distance in meters (haversine approximation)
    R = 6371000
    phi1, phi2 = lat1 * pi / 180, lat2 * pi / 180
    dphi = (lat2 - lat1) * pi / 180
    dlambda = (lon2 - lon1) * pi / 180
    a = (phi1 - phi2)**2 + (cos((phi1 + phi2) / 2) * dlambda)**2
    return R * sqrt(a)

def fetch_sim_locations():
    api = overpy.Overpass(url="https://overpass-api.de/api/interpreter")
    
    countries = [
        {"name": "Netherlands", "code": "NL"},
        {"name": "Belgium", "code": "BE"},
        {"name": "Germany", "code": "DE"},
        {"name": "France", "code": "FR"},
        {"name": "United Kingdom", "code": "GB"}
    ]
    
    new_locations = []
    
    for country in countries:
        c_name = country["name"]
        c_code = country["code"]
        print(f"Expanding SIM data for {c_name}...")
        
        query = f"""
        [out:json][timeout:180];
        area["ISO3166-1"="{c_code}"][admin_level=2]->.searchArea;
        (
          node["leisure"~"sports_centre|amusement_arcade|entertainment_centre"]["name"~"sim|racing|virtual|f1",i](area.searchArea);
          way["leisure"~"sports_centre|amusement_arcade|entertainment_centre"]["name"~"sim|racing|virtual|f1",i](area.searchArea);
          node["sport"="sim_racing"](area.searchArea);
          way["sport"="sim_racing"](area.searchArea);
        );
        out center;
        """
        
        try:
            result = api.query(query)
            count = 0
            for node in result.nodes:
                new_locations.append(process_sim_element(node, c_name, "node"))
            for way in result.ways:
                new_locations.append(process_sim_element(way, c_name, "way"))
            print(f"Found {len(result.nodes) + len(result.ways)} potential SIM locations in {c_name}")
        except Exception as e:
            print(f"Error in {c_name}: {e}")
        
        time.sleep(10) # Overpass friendly
        
    return new_locations

def process_sim_element(element, country, type):
    tags = element.tags
    name = tags.get("name", "N/A")
    website = tags.get("website", tags.get("contact:website", tags.get("url", "N/A")))
    city = tags.get("addr:city", "N/A")
    lat = float(element.lat) if type == "node" else float(element.center_lat)
    lon = float(element.lon) if type == "node" else float(element.center_lon)
    
    return {
        "Name": name,
        "Latitude": lat,
        "Longitude": lon,
        "City": city,
        "Country": country,
        "Website": website,
        "Category": "SIM Racing"
    }

def main():
    data_dir = "../data"
    enriched_file = os.path.join(data_dir, "karting_enriched.csv")
    
    if not os.path.exists(enriched_file):
        print(f"Error: {enriched_file} not found.")
        return

    df_existing = pd.read_csv(enriched_file)
    max_id = df_existing['track_id'].max()
    
    new_data = fetch_sim_locations()
    if not new_data:
        print("No new SIM locations found.")
        return
        
    df_new = pd.DataFrame(new_data)
    
    # Filter out entries that are too generic (not actually racing)
    noise_keywords = ["horse", "greyhound", "stadium", "athletics", "dog racing", "cycling"]
    df_new = df_new[~df_new['Name'].str.lower().str.contains('|'.join(noise_keywords))]
    
    added_count = 0
    final_rows = []
    
    print("Deduplicating against existing dataset...")
    for idx, row in df_new.iterrows():
        is_duplicate = False
        # Check proximity (approx 100m)
        nearby = df_existing[
            (df_existing['Latitude'].between(row['Latitude'] - 0.001, row['Latitude'] + 0.001)) &
            (df_existing['Longitude'].between(row['Longitude'] - 0.001, row['Longitude'] + 0.001))
        ]
        
        for _, existing in nearby.iterrows():
            if calculate_distance(row['Latitude'], row['Longitude'], existing['Latitude'], existing['Longitude']) < 150:
                is_duplicate = True
                # If existing is just Karting, we could update it to hybrid but let's keep it simple for now
                break
        
        if not is_duplicate:
            max_id += 1
            new_row = {col: "N/A" for col in df_existing.columns}
            new_row.update({
                "track_id": max_id,
                "Name": row['Name'],
                "Latitude": row['Latitude'],
                "Longitude": row['Longitude'],
                "City": row['City'],
                "Country": row['Country'],
                "Official Website": row['Website'],
                "Category": "SIM Racing",
                "is_sim": True,
                "is_indoor": False, # Will be refined later
                "is_outdoor": False
            })
            final_rows.append(new_row)
            added_count += 1

    if final_rows:
        df_final = pd.concat([df_existing, pd.DataFrame(final_rows)], ignore_index=True)
        df_final.to_csv(enriched_file, index=False)
        print(f"Success! Added {added_count} new unique SIM racing locations.")
        print(f"New total dataset size: {len(df_final)}")
    else:
        print("No new unique SIM locations to add.")

if __name__ == "__main__":
    main()
