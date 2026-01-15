
import requests

def test_headers(name, headers):
    url = "https://www.equibase.com/static/entry/PRX011426USA-EQB.html"
    print(f"Testing Headers: {name}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content Length: {len(response.content)}")
        if len(response.content) > 5000:
            print("SUCCESS: Content is large.")
            return True
        else:
            print("FAIL: Content is small (likely blocked).")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def run():
    # 1. Minimal (like crawl_equibase.py)
    h1 = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    test_headers("Minimal", h1)
    
    # 2. Curl-like
    h2 = {'User-Agent': 'curl/7.64.1'}
    test_headers("Curl", h2)
    
    # 3. No Headers (Default python-requests)
    h3 = {}
    test_headers("None", h3)
    
    # 4. Full Chrome (what I was using)
    h4 = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    }
    test_headers("Full Chrome", h4)

if __name__ == "__main__":
    run()
