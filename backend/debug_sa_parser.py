import requests
import re
from bs4 import BeautifulSoup
from datetime import date

url = "https://www.equibase.com/static/entry/GP011126USA-EQB.html" # Hardcoded today's GP URL
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0'
}

print(f"Fetching {url}")
resp = requests.get(url, headers=headers)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    print(f"Content Sample (First 1000 chars):\n{resp.text[:1000]}")
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 1. Print all string matches for "Race X" to see what they look like
    print("\n--- 'Race X' Text Matches ---")
    race_matches = soup.find_all(string=re.compile(r'Race\s+\d+', re.IGNORECASE))
    for match in race_matches[:10]: # First 10
        print(f"Match: '{match}' | Parent: {match.parent.name}")
        
    # 2. Try the logic from crawl_entries.py
    print("\n--- Logic Trace ---")
    race_headers = soup.find_all(string=re.compile(r'Race\s+\d+', re.IGNORECASE))
    for header in race_headers:
        print(f"Checking header: '{header}'")
        match = re.search(r'Race\s+(\d+)', header.strip(), re.IGNORECASE)
        if not match:
            print("  Regex failed")
            continue
        print(f"  Race Num: {match.group(1)}")
        
        container = header.find_parent('table')
        if not container:
            container = header.find_parent('div')
        
        print(f"  Container: {container.name if container else 'None'}")
        
        if container:
            table = None
            # Check internal tables
            tables = container.find_all('table')
            print(f"  Internal tables: {len(tables)}")
            for t in tables:
                txt = t.get_text()[:50].replace('\n', ' ')
                print(f"    - Table start: {txt}")
