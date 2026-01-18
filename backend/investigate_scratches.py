
import requests
import logging
from bs4 import BeautifulSoup
from datetime import date
from supabase_client import get_supabase_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_otb_deep():
    url = "https://www.offtrackbetting.com/scratches_changes.html"
    print(f"\nFetching OTB: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        content = r.text
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 1. Check Date
        date_found = "Unknown"
        for t in soup.find_all('table'):
            txt = t.get_text()
            if 'Race Date:' in txt:
                # Extract "Race Date: MM/DD/YYYY"
                import re
                m = re.search(r'Race Date:\s*(\d{1,2}/\d{1,2}/\d{4})', txt)
                if m:
                    date_found = m.group(1)
                break
        print(f"OTB Page Date: {date_found}")
        
        # 2. Search for Horses
        targets = ["Perfect Shances", "Chocolatecroissant", "Game Changer Jolie"]
        
        for target in targets:
            print(f"\nSearching for '{target}':")
            if target in content:
                print(" -> FOUND in raw text")
                # Find the row
                # We reuse the parser logic but loosely
                found_in_row = False
                for row in soup.find_all('tr'):
                    if target in row.get_text():
                        print(f" -> Row Text: {row.get_text(strip=True)}")
                        found_in_row = True
                if not found_in_row:
                    print(" -> Found in text but not in a specific TR? (maybe raw?)")
            else:
                print(" -> NOT FOUND")

    except Exception as e:
        print(f"Error checking OTB: {e}")

def check_db_scratches(track_code, race_date):
    print(f"\nChecking DB for {track_code} on {race_date}")
    supabase = get_supabase_client()
    
    # Check changes table with horse names
    print("Fetching last 20 changes in DB (with related info):")
    
    res = supabase.table('hranalyzer_changes').select('''
        id, change_type, description, created_at,
        entry:hranalyzer_race_entries(
            program_number,
            horse:hranalyzer_horses(horse_name),
            race:hranalyzer_races(track_code, race_number)
        )
    ''').order('created_at', desc=True).limit(20).execute()
    
    found_meyer = False
    
    for row in res.data:
        entry = row.get('entry') or {}
        horse = entry.get('horse') or {}
        race = entry.get('race') or {}
        
        h_name = horse.get('horse_name', 'Unknown')
        if 'Meyer' in h_name:
            found_meyer = True
            print(f"!!! FOUND MEYER: {row}")
            
        if race.get('track_code') == track_code:
            print(f"[{row['created_at']}] {race.get('track_code')} R{race.get('race_number')} #{entry.get('program_number')} {h_name} - {row['change_type']}: {row['description']}")

    if not found_meyer:
        print("\n>>> CONFIRMED: 'Meyer' NOT found in recent DB entries.")

if __name__ == "__main__":
    # check_otb_deep()
    check_db_scratches("GP", date.today().isoformat())
