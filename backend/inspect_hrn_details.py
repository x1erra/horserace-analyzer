
import requests
from bs4 import BeautifulSoup
import re

def inspect_hrn_details():
    url = "https://entries.horseracingnation.com/entries-results/gulfstream-park/2026-01-15"
    print(f"Fetching: {url}")
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # 1. Table Headers
    table = soup.find('table')
    if table:
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        print(f"Table Headers: {headers}")
        
    # 2. Post Time
    # Look for text like "Post Time" or "PM" near "Race 1"
    # Find the container for Race 1
    # Assuming tables are in order, let's look before the first table
    if table:
         prev = table.find_previous_sibling()
         for _ in range(5):
             if not prev: break
             print(f"Preceding Element ({prev.name}): {prev.get_text(strip=True)[:100]}")
             prev = prev.find_previous_sibling()
             
    # Search whole page for "Post Time"
    pt = soup.find(string=re.compile(r'Post Time|PM ET|AM ET'))
    if pt:
         print(f"Found Post Time Text: {pt.strip()} (Parent: {pt.parent.name})")

if __name__ == "__main__":
    inspect_hrn_details()
