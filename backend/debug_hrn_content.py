import requests

url = "https://www.horseracingnation.com/entries"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Content Sample (First 2000 chars):\n{resp.text[:2000]}")
except Exception as e:
    print(f"Error: {e}")
