# MP One: Karting Market Analysis

This project is a comprehensive data enrichment pipeline designed to identify and analyze karting locations globally. It forms the first module of the **MP One** ecosystem, focusing on acquisition metrics and physical site characteristics.

## 🚀 Overview
The pipeline enriches a base list of karting locations with high-fidelity data from multiple sources:
1.  **Google Maps**: Extracts review velocity, sentiment analysis of top reviews, owner activity, hero images, and verified contact details.
2.  **OpenStreetMap (OSM)**: Calculates physical building footprints (sqm) and B2B density within a 2km radius using `osmnx`.

## 📁 Project Structure
To support future scalability (e.g., dashboard integration), the project is organized into modules:
- `data/`: Contains the base and enriched CSV datasets, plus `karting_shapes.geojson`.
- `scripts/`: Python orchestration scripts for the enrichment pipeline.
- `market-analysis/`: (Current) Data processing and analysis module.

## 🛠 Setup & Usage
1.  **Install Dependencies**:
    ```bash
    pip install pandas osmnx playwright deep-translator eurostat openrouteservice geopandas
    playwright install chromium
    ```
2.  **Run Enrichment**:
    ```bash
    # Step 1: Google Maps Data
    python scripts/enrich_karting.py
    # Step 2: OpenStreetMap & Wealth Data
    python scripts/enrich_osm.py
    python scripts/enrich_wealth.py
    # Step 3: Catchment Reach (ORS API Key Required)
    python scripts/enrich_reach.py
    ```
3.  **Access the Dashboard**:
    ```bash
    ./run_dashboard.sh
    ```

## 🔐 Dashboard Access
The dashboard is secured for up to 20 authorized users.
- **URL**: `http://localhost:8501`
- **Default User**: `jaap`
- **Default Password**: `admin123`

## 📈 Roadmap
- [x] Data Extraction & Scraping
- [x] OSM Physical Enrichment
- [x] Eurostat Regional Wealth Enrichment
- [/] Drive-time Reach Isochrones (Running in background)
- [/] Secure Interactive Dashboard (MVP Ready)
