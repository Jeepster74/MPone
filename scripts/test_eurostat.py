import eurostat
import pandas as pd

try:
    print("Fetching dataset 'nama_10r_2hhinc'...")
    dataset = 'nama_10r_2hhinc'
    data = eurostat.get_data_df(dataset)
    print("Dataset fetched successfully!")
    print(data.head())
    print("\nColumns:", data.columns.tolist())
    
    print("Listing all NL regions...")
    nl_data = data[data['geo\\TIME_PERIOD'].str.startswith('NL', na=False)]
    print(nl_data[['unit', 'na_item', 'geo\\TIME_PERIOD']])
    
    print("\nUnique NUTS codes for NL:", nl_data['geo\\TIME_PERIOD'].unique())
    
    # Check if there is data for any year
    year_cols = [c for c in nl33_data.columns if c.isnumeric()]
    print("\nNL33 Data counts per year:")
    print(nl33_data[year_cols].notna().sum())
except Exception as e:
    print(f"Error: {e}")
