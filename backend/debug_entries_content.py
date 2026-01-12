import requests

url = "https://www.equibase.com/static/entry/GP011126USA-EQB.html"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Content Length: {len(resp.text)}")
    print(f"Content Sample: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
