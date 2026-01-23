import pandas as pd
import geopandas as gpd
import eurostat
from shapely.geometry import Point
import os
import ssl

# Bypass SSL verification for Eurostat/GISCO downloads
ssl._create_default_https_context = ssl._create_unverified_context

# Resolve paths relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# GISCO NUTS GeoJSON URL (NUTS 2021, Level 2, 4326)
NUTS_GEOJSON_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326_LEVL_2.geojson"

def enrich_with_wealth():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print("Loading track data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Idempotency: Drop existing NUTS and wealth columns if they exist
    cols_to_clean = ['NUTS_ID', 'NUTS_NAME', 'disposable_income_pps', 'wealth_data_year']
    df = df.drop(columns=[c for c in cols_to_clean if c in df.columns])
    
    # Check if we have lat/lon
    if 'Latitude' not in df.columns or 'Longitude' not in df.columns:
        print("Error: Latitude or Longitude columns missing.")
        return

    # Convert to GeoDataFrame
    # Drop rows with missing coordinates
    gdf_tracks = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
        crs="EPSG:4326"
    )

    print("Downloading NUTS-2 shapefiles from GISCO...")
    try:
        nuts_gdf = gpd.read_file(NUTS_GEOJSON_URL)
        print(f"Loaded {len(nuts_gdf)} NUTS-2 regions.")
        print("NUTS Columns:", nuts_gdf.columns.tolist())
    except Exception as e:
        print(f"Error loading NUTS GeoJSON: {e}")
        return

    print("Performing Spatial Join (Tracks -> NUTS-2)...")
    # 1. Primary spatial join (Within)
    joined = gpd.sjoin(gdf_tracks, nuts_gdf[['NUTS_ID', 'NUTS_NAME', 'geometry']], how="left", predicate="within")
    
    # 2. Handle points just outside polygons (coastal/borders) using nearest neighbor
    missing_nuts = joined['NUTS_ID'].isna()
    if missing_nuts.any():
        print(f"Assigning {missing_nuts.sum()} tracks to nearest NUTS region...")
        # Get tracks that matched nothing
        unmatched = gdf_tracks[missing_nuts].copy()
        # Find nearest
        nearest = gpd.sjoin_nearest(unmatched, nuts_gdf[['NUTS_ID', 'NUTS_NAME', 'geometry']], how="left", distance_col="dist")
        # Update joined dataframe
        joined.loc[missing_nuts, 'NUTS_ID'] = nearest['NUTS_ID'].values
        joined.loc[missing_nuts, 'NUTS_NAME'] = nearest['NUTS_NAME'].values

    print("Fetching Disposable Income data from Eurostat (nama_10r_2hhinc)...")
    try:
        # Fetching latest data
        income_data = eurostat.get_data_df('nama_10r_2hhinc')
        
        # We want 'Disposable income, net' (B5N) and unit 'PPS_EU27_2020_HAB'
        income_filtered = income_data[
            (income_data['unit'] == 'PPS_EU27_2020_HAB') & 
            (income_data['na_item'] == 'B5N')
        ].copy()
        
        # Eurostat columns are numeric years
        year_columns = [col for col in income_filtered.columns if col.isnumeric()]
        year_columns.sort(reverse=True)
        
        # Latest wealth mapping
        income_map = income_filtered.melt(
            id_vars=['geo\\TIME_PERIOD'], 
            value_vars=year_columns, 
            var_name='year', 
            value_name='wealth_index'
        )
        latest_wealth = income_map.dropna(subset=['wealth_index']).sort_values('year', ascending=False).drop_duplicates('geo\\TIME_PERIOD')
        latest_wealth = latest_wealth[['geo\\TIME_PERIOD', 'wealth_index', 'year']]
        latest_wealth.columns = ['NUTS_ID', 'disposable_income_pps', 'wealth_data_year']
        
        # UK Fallback: Since UK is missing from modern Eurostat regional tables,
        # we add a national average proxy for UK regions based on ONS/OECD trends (~21,500 PPS)
        if 'UK' not in latest_wealth['NUTS_ID'].values:
            print("Adding manual UK National Average fallback...")
            uk_fallback = pd.DataFrame([{
                'NUTS_ID': 'UK', 
                'disposable_income_pps': 21500.0, 
                'wealth_data_year': '2021 (Estimated)'
            }])
            latest_wealth = pd.concat([latest_wealth, uk_fallback], ignore_index=True)
            
        print(f"Fetched wealth data for {len(latest_wealth)} regions.")
    except Exception as e:
        print(f"Error fetching Eurostat data: {e}")
        return

    print("Merging Wealth Data into Dashboard with Fallbacks...")
    # 1. Join on NUTS-2
    joined = joined.merge(latest_wealth, on='NUTS_ID', how='left')
    
    # 2. Add fallbacks for missing data
    # Create NUTS-1 and NUTS-0 columns for fallback lookups
    joined['NUTS1'] = joined['NUTS_ID'].str[:3]
    joined['NUTS0'] = joined['NUTS_ID'].str[:2]
    
    # Identify missing
    missing_mask = joined['disposable_income_pps'].isna()
    print(f"Initial missing wealth data: {missing_mask.sum()} / {len(joined)}")
    
    if missing_mask.any():
        print("Attempting NUTS-1 Fallback...")
        # Merge on NUTS-1
        fallback_n1 = latest_wealth.rename(columns={
            'NUTS_ID': 'NUTS1', 
            'disposable_income_pps': 'pps_n1',
            'wealth_data_year': 'year_n1'
        })
        joined = joined.merge(fallback_n1, on='NUTS1', how='left')
        
        # Fill missing with NUTS-1
        mask = joined['disposable_income_pps'].isna() & joined['pps_n1'].notna()
        joined.loc[mask, 'disposable_income_pps'] = joined.loc[mask, 'pps_n1']
        joined.loc[mask, 'wealth_data_year'] = joined.loc[mask, 'year_n1']
        
        # 3. NUTS-0 Fallback (National average)
        print("Attempting NUTS-0 (National) Fallback...")
        fallback_n0 = latest_wealth.rename(columns={
            'NUTS_ID': 'NUTS0',
            'disposable_income_pps': 'pps_n0',
            'wealth_data_year': 'year_n0'
        })
        joined = joined.merge(fallback_n0, on='NUTS0', how='left')
        
        mask = joined['disposable_income_pps'].isna() & joined['pps_n0'].notna()
        joined.loc[mask, 'disposable_income_pps'] = joined.loc[mask, 'pps_n0']
        joined.loc[mask, 'wealth_data_year'] = joined.loc[mask, 'year_n0']

    # Final count of missing
    final_missing = joined['disposable_income_pps'].isna().sum()
    print(f"Final missing wealth data: {final_missing} / {len(joined)}")
    if final_missing > 0:
        missing_countries = joined[joined['disposable_income_pps'].isna()]['Country'].unique()
        print(f"Missing data for countries: {missing_countries}")

    # Cleanup internal columns
    cols_to_drop = ['geometry', 'index_right', 'NUTS1', 'NUTS0', 'pps_n1', 'year_n1', 'pps_n0', 'year_n0']
    cols_to_drop = [c for c in cols_to_drop if c in joined.columns]
    final_df = joined.drop(columns=cols_to_drop)
        
    # Save results
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Success! Enriched data saved to {OUTPUT_FILE}")
    
    # Summary of wealth stats
    print("\nWealth Data Summary (PPS):")
    print(final_df['disposable_income_pps'].describe())

if __name__ == "__main__":
    enrich_with_wealth()
