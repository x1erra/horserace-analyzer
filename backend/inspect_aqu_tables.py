
import requests
from bs4 import BeautifulSoup

def inspect_aqu_all_tables():
    url = "https://entries.horseracingnation.com/entries-results/aqueduct/2026-01-14"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables total.")
    
    for i, table in enumerate(tables):
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        print(f"\nTable {i} Headers: {headers}")
        if 'Horse' in str(headers) or 'ML' in str(headers):
             print(f"  -> Likely an ENTRY table.")
        else:
             print(f"  -> Likely NOT an entry table.")

if __name__ == "__main__":
    inspect_aqu_all_tables()
