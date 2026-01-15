
import requests
import datetime

def test_url(url, description):
    print(f"Testing {description}: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content Length: {len(response.content)}")
        if response.status_code == 200:
            print("Snippet:", response.text[:200])
            return response.text
        else:
            print("Failed.")
    except Exception as e:
        print(f"Error: {e}")
    return None

def run():
    # 1. Test Static Entry Index
    index_html = test_url("https://www.equibase.com/static/entry/index.html", "Static Entry Index")
    
    # 2. If index works, try to find a link for a track today or tomorrow?
    # Actually, let's try to construct a probable static entry URL.
    # Pattern often seen: https://www.equibase.com/static/entry/GP011426USA-EQB.html (Track+MM+DD+YY+USA-EQB.html)
    # Date: 2026-01-14 (User's current time)
    
    today = datetime.date.today()
    mm = today.strftime('%m')
    dd = today.strftime('%d')
    yy = today.strftime('%y')
    
    # Try a few common tracks
    tracks = ['GP', 'TAM', 'AQU', 'PRX'] 
    
    for track in tracks:
        # Construct potential static entry URL
        # Format guess: /static/entry/GP011426USA-EQB.html
        url = f"https://www.equibase.com/static/entry/{track}{mm}{dd}{yy}USA-EQB.html"
        test_url(url, f"Probable Entry Page for {track}")

if __name__ == "__main__":
    run()
