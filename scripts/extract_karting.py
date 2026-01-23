import overpy
import pandas as pd
import time
import ssl
import os

# Bypass SSL verification globally for this environment
ssl._create_default_https_context = ssl._create_unverified_context

def fetch_racing_locations():
    api = overpy.Overpass(url="https://overpass-api.de/api/interpreter")
    
    countries = [
        {"name": "Netherlands", "code": "NL"},
        {"name": "Belgium", "code": "BE"},
        {"name": "Germany", "code": "DE"},
        {"name": "France", "code": "FR"},
        {"name": "United Kingdom", "code": "GB"}
    ]
    
    output_file = "../data/karting_locations.csv"
    all_locations = []
    
    # We will overwrite and re-fetch to ensure categorization and filtering is consistent
    # instead of resuming from a potentially noisy dataset.
    # However, I'll keep the logic if we wanted to resume later.
    
    for country in countries:
        country_name = country["name"]
        country_code = country["code"]
        print(f"Fetching data for {country_name} ({country_code})...")
        
        # Super-refined Query:
        # 1. sport=karting OR sport=sim_racing
        # 2. leisure=track AND (name~kart OR name~sim)
        # 3. name~karting OR name~sim_racing
        query = f"""
        [out:json][timeout:300];
        area["ISO3166-1"="{country_code}"][admin_level=2]->.searchArea;
        (
          // Karting specific
          node["sport"="karting"](area.searchArea);
          way["sport"="karting"](area.searchArea);
          
          // SIM Racing specific
          node["sport"="sim_racing"](area.searchArea);
          way["sport"="sim_racing"](area.searchArea);
          
          // Name-based filtering for leisure=track to avoid generic tracks
          node["leisure"="track"]["name"~"kart|sim|racing",i](area.searchArea);
          way["leisure"="track"]["name"~"kart|sim|racing",i](area.searchArea);
          
          // Any nodes/ways with karting or sim racing in the name
          node["name"~"karting|sim racing|simracing",i](area.searchArea);
          way["name"~"karting|sim racing|simracing",i](area.searchArea);
        );
        out center;
        """
        
        retries = 5
        delay = 45
        
        while retries > 0:
            try:
                result = api.query(query)
                
                count = 0
                for node in result.nodes:
                    all_locations.append(process_element(node, country_name, "node"))
                    count += 1
                for way in result.ways:
                    all_locations.append(process_element(way, country_name, "way"))
                    count += 1
                    
                print(f"Successfully fetched {count} elements in {country_name}")
                break
                
            except Exception as e:
                print(f"Error fetching data for {country_name} (Retries left: {retries-1}): {e}")
                retries -= 1
                if retries > 0:
                    print(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"Failed to fetch data for {country_name} after multiple attempts.")
            
        time.sleep(20)
        
    return all_locations

def process_element(element, country, type):
    tags = element.tags
    name = tags.get("name", "N/A")
    website = tags.get("website", tags.get("contact:website", tags.get("url", "N/A")))
    city = tags.get("addr:city", "N/A")
    
    sport = tags.get("sport", "").lower()
    lower_name = name.lower()
    
    categories = []
    
    # Check for Karting
    if "karting" in sport or "kart" in lower_name or tags.get("leisure") == "track" and "kart" in lower_name:
        categories.append("Karting")
    
    # Check for SIM Racing
    if "sim_racing" in sport or "sim racing" in lower_name or "simracing" in lower_name:
        categories.append("SIM Racing")
        
    # Default if tags were weird but it was in the query
    if not categories:
        if "kart" in lower_name or "kart" in sport:
            categories.append("Karting")
        elif "sim" in lower_name or "sim" in sport:
            categories.append("SIM Racing")
        else:
            categories.append("Karting") # Assumption based on original query context
            
    category_str = " & ".join(sorted(list(set(categories)))) if categories else "Karting"

    if type == "node":
        lat = float(element.lat)
        lon = float(element.lon)
    else:
        if hasattr(element, 'center_lat') and element.center_lat:
            lat = float(element.center_lat)
            lon = float(element.center_lon)
        elif hasattr(element, 'nodes') and len(element.nodes) > 0:
            lat = float(element.nodes[0].lat)
            lon = float(element.nodes[0].lon)
        else:
            lat, lon = "N/A", "N/A"

    return {
        "Name": name,
        "Latitude": lat,
        "Longitude": lon,
        "City": city,
        "Country": country,
        "Website": website,
        "Category": category_str
    }

if __name__ == "__main__":
    data = fetch_racing_locations()
    if not data:
        print("No data found.")
    else:
        df = pd.DataFrame(data)
        # Deduplicate
        df = df.drop_duplicates(subset=["Name", "Latitude", "Longitude"])
        
        # One last filter to be absolutely sure we don't have generic tracks that don't belong
        # If Category is Karting but name contains "Athletics", "Stadium", "Horse", etc, we might want to be careful.
        # But our query was already quite specific with name filters on leisure=track.
        
        output_file = "../data/karting_locations.csv"
        df.to_csv(output_file, index=False)
        
        print("\nSummary of locations found per country:")
        if "Country" in df.columns:
            summary = df.groupby(["Country", "Category"]).size()
            print(summary)
        
        print(f"\nTotal unique locations: {len(df)}")
        print(f"Results saved to {output_file}")
