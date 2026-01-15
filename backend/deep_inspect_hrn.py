
import requests
from bs4 import BeautifulSoup
import re

def deep_inspect_hrn():
    url = "https://entries.horseracingnation.com/entries-results/gulfstream-park/2026-01-15"
    print(f"Deeply Fetching HRN: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Let's search for "Race 1" and look at everything around it
    race1_search = soup.find(string=re.compile(r'Race 1', re.IGNORECASE))
    if race1_search:
        parent = race1_search.parent
        # Go up a few levels to see the container
        for _ in range(3):
            if parent.parent: parent = parent.parent
        
        print("\n--- Race 1 Container Content ---")
        print(parent.get_text(" | ", strip=True)[:1000])
        
        # Look for specific metadata patterns
        # Distance: e.g. "6 Furlongs", "1 Mile"
        # Surface: "Dirt", "Turf", "Synthetic"
        # Purse: "$40,000"
        
        text = parent.get_text(" ", strip=True)
        dist = re.search(r'(\d+\s*(?:Furlongs|Miles|Yards))', text, re.IGNORECASE)
        surf = re.search(r'(Dirt|Turf|Synthetic|All Weather)', text, re.IGNORECASE)
        purse = re.search(r'Purse\s*[:\s]*(\$\d{1,3}(?:,\d{3})*)', text, re.IGNORECASE)
        
        print(f"\nExtracted from text:")
        print(f"Distance: {dist.group(1) if dist else 'Not Found'}")
        print(f"Surface: {surf.group(1) if surf else 'Not Found'}")
        print(f"Purse: {purse.group(1) if purse else 'Not Found'}")

    # Look for list items or specific headers
    print("\n--- Looking for specific classes ---")
    detail_divs = soup.find_all('div', class_=re.compile(r'detail|info|meta|conditions', re.IGNORECASE))
    for d in detail_divs[:5]:
        print(f"Found div with class {d.get('class')}: {d.get_text(strip=True)[:100]}")

if __name__ == "__main__":
    deep_inspect_hrn()
