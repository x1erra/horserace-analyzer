import sys
import os

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawl_scratches import parse_track_changes
import requests
from bs4 import BeautifulSoup

def test_aqueduct_cancellation():
    url = "https://www.equibase.com/static/latechanges/html/latechangesAQU-USA.html"
    print(f"Fetching {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch: {response.status_code}")
        return

    html = response.text
    changes = parse_track_changes(html, "AQU")
    
    cancellations = [c for c in changes if c['change_type'] == 'Race Cancelled']
    
    print(f"Found {len(changes)} total changes.")
    print(f"Found {len(cancellations)} cancellations.")
    
    for c in cancellations:
        print(f"Race {c['race_number']}: {c['description']}")

if __name__ == "__main__":
    test_aqueduct_cancellation()
