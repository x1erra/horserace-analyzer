import cloudscraper

url = "https://www.equibase.com/static/entry/SA011126USA-EQB.html"

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

print(f"Fetching {url} with cloudscraper...")
try:
    resp = scraper.get(url, timeout=15)
    print(f"Status: {resp.status_code}")
    print(f"Content Sample (First 1000 chars):\n{resp.text[:1000]}")
except Exception as e:
    print(f"Error: {e}")
