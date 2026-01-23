# MP One: Karting Market Analysis

This project is a comprehensive data enrichment pipeline designed to identify and analyze karting locations globally. It forms the first module of the **MP One** ecosystem, focusing on acquisition metrics and physical site characteristics.

## 🚀 Overview
The pipeline enriches a base list of karting locations with high-fidelity data from multiple sources:
1.  **Google Maps**: Extracts review velocity, sentiment analysis of top reviews, owner activity, hero images, and verified contact details.
2.  **OpenStreetMap (OSM)**: Calculates physical building footprints (sqm) and B2B density within a 2km radius using `osmnx`.

## 📁 Project Structure
To support future scalability (e.g., dashboard integration), the project is organized into modules:
- `data/`: Contains the base and enriched CSV datasets.
- `scripts/`: Python orchestration scripts for the enrichment pipeline.
- `market-analysis/`: (Current) Data processing and analysis module.

## 🛠 Setup & Usage
1.  **Install Dependencies**:
    ```bash
    pip install pandas osmnx playwright deep-translator
    playwright install chromium
    ```
2.  **Run Enrichment**:
    ```bash
    # Step 1: Google Maps Data
    python scripts/enrich_karting.py
    # Step 2: OpenStreetMap Data
    python scripts/enrich_osm.py
    ```

## 📈 Roadmap
- [x] Data Extraction & Scraping
- [x] OSM Physical Enrichment
- [ ] Interactive Dashboard (Next Phase)
- [ ] Market Penetration Analytics
