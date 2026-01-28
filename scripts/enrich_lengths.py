import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import osmnx as ox
from shapely.geometry import Point, LineString, MultiLineString
import re
import os
import argparse
import time
import sys

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
DEFAULT_BATCH_SIZE = 50

# Regex patterns for track length
LENGTH_PATTERNS = [
    r'(\d{2,4})\s?m(?!\w)',
    r'(\d{2,4})\s?meter',
    r'(\d{2,4})\s?metres',
    r'length:\s?(\d{2,4})',
    r'länge:\s?(\d{2,4})',
    r'longueur:\s?(\d{2,4})',
    r'lunghezza:\s?(\d{2,4})',
    r'lengte:\s?(\d{2,4})'
]

def safe_save(df, output_file):
    try:
        if os.path.exists(output_file):
            disk_df = pd.read_csv(output_file)
            disk_df.set_index('track_id', inplace=True)
            df_temp = df.set_index('track_id')
            disk_df.update(df_temp)
            disk_df.reset_index().to_csv(output_file, index=False)
        else:
            df.to_csv(output_file, index=False)
        print(f"--- Safe Save Complete ---")
    except Exception as e:
        print(f"Error during safe save: {e}")

def get_osm_track_length(lat, lon):
    point = (lat, lon)
    try:
        tags = {'leisure': 'track', 'sport': 'karting', 'highway': 'raceway'}
        features = ox.features_from_point(point, tags=tags, dist=500)
        if features.empty: return 0
        
        tracks = features[features.geometry.type.isin(['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'])]
        if tracks.empty: return 0
        
        tracks_proj = ox.projection.project_gdf(tracks)
        lengths = []
        for _, row in tracks_proj.iterrows():
            geom = row.geometry
            if geom.geom_type in ['LineString', 'MultiLineString']:
                lengths.append(geom.length)
            elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                lengths.append(geom.boundary.length)
        
        return round(max(lengths), 0) if lengths else 0
    except: return 0

async def scrape_track_length(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)
        text = await page.inner_text('body')
        text = text.lower()
        found_lengths = []
        for pattern in LENGTH_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                val = int(match.group(1))
                if 100 <= val <= 3000: found_lengths.append(val)
        return max(found_lengths) if found_lengths else None
    except: return None

async def main():
    parser = argparse.ArgumentParser(description='Enrich track lengths.')
    parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILE): return

    df = pd.read_csv(INPUT_FILE)
    for col in ['track_length_m', 'website_track_length_m']:
        if col not in df.columns: df[col] = 0

    # Prioritize those that have neither
    mask = ((df['track_length_m'] == 0) | (df['track_length_m'].isna())) & \
           ((df['website_track_length_m'] == 0) | (df['website_track_length_m'].isna()))
    
    to_process = df[mask].head(args.batch)
    if to_process.empty:
        # Fallback to those missing at least one
        mask = ((df['track_length_m'] == 0) | (df['website_track_length_m'] == 0))
        to_process = df[mask].head(args.batch)

    print(f"Processing {len(to_process)} locations...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        for index, row in to_process.iterrows():
            print(f"Processing: {row['Name']}")
            
            # 1. OSM
            if pd.isna(row['track_length_m']) or row['track_length_m'] == 0:
                osm_len = get_osm_track_length(row['Latitude'], row['Longitude'])
                if osm_len > 0:
                    print(f"   OSM Length: {osm_len}m")
                    df.at[index, 'track_length_m'] = osm_len

            # 2. Website
            if pd.isna(row['website_track_length_m']) or row['website_track_length_m'] == 0:
                url = row['Official Website']
                if pd.notna(url) and url != 'N/A':
                    page = await browser.new_page()
                    web_len = await scrape_track_length(page, url)
                    await page.close()
                    if web_len:
                        print(f"   Web Length: {web_len}m")
                        df.at[index, 'website_track_length_m'] = web_len
                    else:
                        df.at[index, 'website_track_length_m'] = -1
            
            if (index + 1) % 5 == 0:
                safe_save(df, OUTPUT_FILE)
            
            await asyncio.sleep(1)

        await browser.close()

    safe_save(df, OUTPUT_FILE)
    print("Done.")

if __name__ == "__main__":
    ox.settings.use_cache = True
    asyncio.run(main())
