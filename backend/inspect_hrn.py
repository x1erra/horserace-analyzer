
import requests
from bs4 import BeautifulSoup

def inspect_hrn_index():
    url = "https://entries.horseracingnation.com/"
    print(f"Fetching HRN Index: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find all track links
        # Attempt to find links that look like track pages
        links = soup.find_all('a', href=True)
        
        print(f"Found {len(links)} links. Filtering for potential track pages...")
        
        track_links = []
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)
            # HRN likely uses format /entries-results/{track}/{date} or similar
            if 'entries-results' in href:
                print(f"Track Link: {text} -> {href}")
                track_links.append(href)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_hrn_index()
