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
3.  **Launch Premium Intelligence Dashboard**:
    ```bash
    # Open your terminal and run:
    ./run_premium_dashboard.sh
    ```

## 🏎️ Premium Dashboard (Next-Gen)
The new **Vite + React + FastAPI** dashboard follows the **'Nano Banana'** aesthetic with MP Motorsport branding.
- **UX**: Mapbox heatmaps, side-pane 'Golden Records', and a permanent wishlist.
- **Deployment**: Powered by **Docker** for local use and **Google Cloud Run** for production.
- **Access**: `http://localhost:8000` (FastAPI + React Bundle)
- **Deployment Guide**: See [DEPLOY_GCP.md](file:///Users/jaap.vanoort/Documents/MP%20One/Market%20Analysis/premium-dashboard/DEPLOY_GCP.md) for cloud instructions.
- **Credential Creation**: Use `premium-dashboard/backend/users.json` to manage access for up to 20 users.

## 📁 Data Dictionary (Glossary)
- **Disposable Income (PPS)**: Regional wealth index from Eurostat.
- **Catchment Area (km²)**: 30-min drive-time reach from ORS API.
- **Building SQM**: Physical footprint from OSM polygons.

## 📈 Roadmap
- [x] Data Extraction & Scraping
- [x] OSM Physical Enrichment
- [x] Eurostat Regional Wealth Enrichment
- [/] Drive-time Reach Isochrones (Running in background; Safe-Save active; ~2,000 tracks pending)
- [x] Premium 'Nano Banana' Dashboard (V1 Launch)
- [x] Google Cloud Environment Setup
