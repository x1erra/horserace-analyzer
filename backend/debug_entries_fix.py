
import requests
import cloudscraper
from bs4 import BeautifulSoup
import re
from datetime import date

# Use CloudScraper to match production
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def debug_parsing():
    # Use a track and date that was failing in logs (e.g. today or tomorrow)
    # The logs showed GP was failing for 2026-01-12
    # Adjust date to today/actual date
    race_date = date.today()
    date_str = race_date.strftime('%m%d%y')
    track_code = "GP" 
    
    url = f"https://www.equibase.com/static/entry/{track_code}{date_str}USA-EQB.html"
    print(f"Fetching {url}...")
    
    try:
        resp = scraper.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"Failed to fetch: {resp.status_code}")
            return
            
        html_content = resp.text
        print(f"Fetched {len(html_content)} bytes")
        
        # Save HTML for inspection
        with open("debug_equibase.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("Saved debug_equibase.html")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Test 1: Race Headers
        print("\n--- Testing Race Header Regex ---")
        race_headers = soup.find_all(string=re.compile(r'Race\s+\d+', re.IGNORECASE))
        print(f"Found {len(race_headers)} potential headers")
        
        for i, h in enumerate(race_headers):
            print(f"Header {i}: '{h.strip()}' parent: {h.parent.name}")
            
        if not race_headers:
            print("CRITICAL: No race headers found. Check pattern.")
            
        # Test 2: Entry Tables
        print("\n--- Testing Entry Tables ---")
        tables = soup.find_all('table')
        pgm_tables = [t for t in tables if 'Program' in t.get_text() or 'Pgm' in t.get_text()]
        print(f"Found {len(pgm_tables)} tables with 'Program'/'Pgm'")
        
        # Check actual logic from crawl_entries.py
        # ... logic replication ...
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_parsing()
