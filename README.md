# GeoSpell: Satellite Imagery Name Maker
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://geo-spell.streamlit.app/)
A Python pipeline that downloads satellite imagery from NASA's "Your Name in Landsat" outreach program, audits the geographical metadata, repairs broken URLs, and generates custom name posters in PDF format.

## Setup
`pip install -r requirements.txt`

## Pipeline Execution Order
1. **`scraper.py`**: Downloads the high-res physical image assets into A-Z folders.
2. **`metadata_scraper.py`**: Scans the physical directory and builds a base metadata database, cross-referencing live articles to map dates and coordinates.
3. **`hotfix_urls.py`**: Targets and repairs Google Maps URL anomalies by mathematically isolating DOM elements to prevent data leakage.
4. **`engine.py`**: Reads the final database, handles ASCII/URL-character decoding for file matching, and stitches the images and metadata into a high-resolution PDF.

## Project Structure
'''
/nasa-landsat-pdf-generator
│
├── metadata.json           # Your clean, verified dataset
├── requirements.txt        # selenium, pillow, webdriver-manager, requests
├── README.md               # Updated execution order (below)
│
├── /pipeline
│   ├── scraper.py               # RUN FIRST: Downloads physical assets
│   ├── metadata_scraper.py      # RUN SECOND: Performs inventory & date crawling
│   └── hotfix_urls.py           # RUN THIRD: Targeted repair for map links
│
├── /generator
│   └── engine.py           # RUN FOURTH: Decodes keys & generates PDF
│
└── /nasa_alphabet_database # Folder with A-Z image folders
