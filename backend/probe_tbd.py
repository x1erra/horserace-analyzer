import sys
import os
from datetime import date
def improved_fetch_hrn_entries(track_code, race_date):
    import requests
    import re
    from bs4 import BeautifulSoup
    slug = {'PRX': 'parx-racing', 'TAM': 'tampa-bay-downs'}.get(track_code)
    url = f"https://entries.horseracingnation.com/entries-results/{slug}/{race_date.strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    all_tables = soup.find_all('table')
    entry_tables = []
    for table in all_tables:
        hdrs = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if any(h in hdrs for h in ['#', 'pp', 'horse', 'ml']):
            entry_tables.append(table)
            
    results = []
    for idx, table in enumerate(entry_tables):
        race_num = idx + 1
        post_time = None
        purse = None
        distance = None
        surface = None
        
        # 1. TRY CLASS DETECTION (RESULTS PAGE)
        header = soup.find(id=f"race-{race_num}")
        if header:
            time_tag = header.find('time', class_='race-time')
            if time_tag:
                post_time = time_tag.get_text(strip=True)
            
            # Find the row containing purse/distance/surface
            # It's usually the next sibling of the parent h2
            parent_h2 = header.find_parent('h2')
            if parent_h2:
                details_row = parent_h2.find_next_sibling('div', class_='row')
                if details_row:
                    p_tag = details_row.find(class_='race-purse')
                    if p_tag: purse = p_tag.get_text(strip=True).replace('Purse:', '').strip()
                    
                    d_tag = details_row.find(class_='race-distance')
                    if d_tag: distance = d_tag.get_text(strip=True)
                    
                    s_tag = details_row.find(class_='race-restrictions') # Surface is often here too
                    if s_tag: surface = s_tag.get_text(strip=True)

        # 2. FALLBACK TO SIBLING REGEX (ENTRY PAGE)
        if not post_time or not purse:
            prev = table.find_previous_sibling()
            for _ in range(5):
                if not prev: break
                txt = prev.get_text(" ", strip=True)
                if not post_time:
                    pt_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', txt, re.IGNORECASE)
                    if pt_match: post_time = pt_match.group(1)
                if not purse:
                    purse_match = re.search(r'Purse\s*[:\s]*(\$\d{1,3}(?:,\d{3})*)', txt, re.IGNORECASE)
                    if purse_match: purse = purse_match.group(1)
                prev = prev.find_previous_sibling()
                
        results.append({'race_number': race_num, 'post_time': post_time, 'purse': purse, 'distance': distance, 'surface': surface})
    return results

def probe():
    target_date = date(2026, 1, 14)
    for track in ['PRX', 'TAM']:
        print(f"\n--- Probing {track} for {target_date} ---")
        races = improved_fetch_hrn_entries(track, target_date)
        for race in races:
            print(f"Race {race['race_number']}: Post Time = {race['post_time']}, Purse = {race['purse']}, Dist = {race['distance']}, Surf = {race['surface']}")

if __name__ == "__main__":
    probe()
