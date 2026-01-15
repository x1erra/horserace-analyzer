
import requests
from bs4 import BeautifulSoup
import re

def inspect_hrn_race():
    # Using Gulfstream for Jan 15 as seen in the index links
    url = "https://entries.horseracingnation.com/entries-results/gulfstream-park/2026-01-15"
    print(f"Fetching HRN Race Page: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"Status: {r.status_code}")
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find all Race Headers
        # Look for "Race X"
        markers = soup.find_all(string=re.compile(r'Race\s+\d+'))
        print(f"Found {len(markers)} 'Race X' markers.")
        for m in markers[:3]:
            print(f"Marker: {m.strip()} (Parent: {m.parent.name})")
            
        # Find table rows with Program Numbers?
        # Look for common horse names or standard table structures
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables.")
        
        if tables:
            print("First table sample rows:")
            rows = tables[0].find_all('tr')
            for row in rows[:5]:
                print(row.get_text(" | ", strip=True))
                
        # Dump a small part of content if no tables found
        if not tables:
            print("No tables found. Dumping race container structure...")
            # Look for div class="race" or similar?
            divs = soup.find_all('div', class_=re.compile(r'race|entry'))
            for d in divs[:2]:
                print(f"Div Class: {d.get('class')}")
                print(d.get_text(" | ", strip=True)[:200])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_hrn_race()
