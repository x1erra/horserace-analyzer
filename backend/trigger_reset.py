
import requests
import json
import time

def trigger_reset():
    url = "http://localhost:5001/api/crawl-changes"
    print(f"Triggering Reset & Crawl: {url}?reset=true")
    try:
        r = requests.post(url, params={'reset': 'true'}, timeout=60)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Error triggering reset: {e}")

if __name__ == "__main__":
    trigger_reset()
