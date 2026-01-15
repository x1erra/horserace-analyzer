
import requests
from bs4 import BeautifulSoup

def inspect_aqueduct():
    url = "https://entries.horseracingnation.com/entries-results/aqueduct/2026-01-14"
    print(f"Fetching: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    table = soup.find('table')
    if table:
        print("\n--- Headers ---")
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        print(headers)
        
        print("\n--- Sample Row ---")
        row = table.find('tr', class_=lambda x: x != 'header')
        if not row:
            rows = table.find_all('tr')
            if len(rows) > 1: row = rows[1]
            
        if row:
            cols = row.find_all('td')
            for i, col in enumerate(cols):
                print(f"Col {i}: {col.get_text('|', strip=True)}")

if __name__ == "__main__":
    inspect_aqueduct()
