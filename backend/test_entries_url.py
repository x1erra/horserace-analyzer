import requests
from datetime import datetime

# Test known tracks for Jan 11, 2026
tracks = ['GP', 'AQU', 'SA', 'TAM', 'FG'] # Gulfstream, Aqueduct, Santa Anita, Tampa, Fair Grounds
date_str = "011126" # Today is Jan 11, 2026

for track in tracks:
    url = f"https://www.equibase.com/static/entry/{track}{date_str}USA-EQB.html"
    print(f"Testing {url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            print(f"SUCCESS: Found entries for {track}! Content length: {len(resp.text)}")
            if "Race 1" in resp.text:
                print("Verified content contains 'Race 1'")
        else:
            print(f"FAILED: {resp.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")
