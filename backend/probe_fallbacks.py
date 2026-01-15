
import requests

def probe_brisnet():
    url = "https://www.brisnet.com/racing/"
    print(f"Testing Brisnet: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"Status: {r.status_code}")
        print(f"Length: {len(r.content)}")
    except Exception as e:
        print(f"Error: {e}")

def probe_hrn():
    url = "https://entries.horseracingnation.com/"
    print(f"Testing HRN: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"Status: {r.status_code}")
        print(f"Length: {len(r.content)}")
        if r.status_code == 200:
             print("Sample content (first 500):")
             print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    probe_brisnet()
    probe_hrn()
