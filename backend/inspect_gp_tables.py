
import requests
from bs4 import BeautifulSoup

def inspect_gp_all_tables():
    url = "https://entries.horseracingnation.com/entries-results/gulfstream-park/2026-01-15"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables total.")
    
    for i, table in enumerate(tables):
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        print(f"\nTable {i} Headers: {headers}")

if __name__ == "__main__":
    inspect_gp_all_tables()
