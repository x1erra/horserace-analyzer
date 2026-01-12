import requests

sources = [
    "https://www.horseracingnation.com/entries",
    "https://www.brisnet.com/racing"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

for url in sources:
    print(f"Testing {url}...")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Content Length: {len(resp.text)}")
        if resp.status_code == 200:
            print(f"Sample: {resp.text[:200]}...")
    except Exception as e:
        print(f"Error accessing {url}: {e}")
