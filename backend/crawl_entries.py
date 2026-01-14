"""
Crawl Equibase Entries (Upcoming Races)
Parses HTML from Equibase to get upcoming race data
Uses Selenium with Headless Chrome to bypass WAF
"""
import requests
import re
import logging
import time
import os
from datetime import datetime, date
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from supabase_client import get_supabase_client
from crawl_equibase import get_or_create_track, get_or_create_participant, COMMON_TRACKS

logger = logging.getLogger(__name__)

def get_driver():
    """Configure and return a headless Chrome driver"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=375,812") # Mobile dimensions
    
    # Use Mobile User Agent (often bypasses desktop WAF)
    options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1")
    
    service = None
    
    # Check for Chromium binary
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        logger.info(f"Found Chromium binary at /usr/bin/chromium")
    elif os.path.exists("/usr/bin/chromium-browser"):
        options.binary_location = "/usr/bin/chromium-browser"
        logger.info(f"Found Chromium binary at /usr/bin/chromium-browser")

    # Check for ChromeDriver binary
    driver_paths = ["/usr/bin/chromedriver", "/usr/lib/chromium-browser/chromedriver", "/usr/bin/chromium-driver"]
    found_driver = None
    
    for path in driver_paths:
        if os.path.exists(path):
            found_driver = path
            logger.info(f"Found ChromeDriver at {path}")
            break
            
    if found_driver:
        service = Service(executable_path=found_driver)
    else:
        logger.warning("Could not find system chromedriver, relying on Selenium Manager...")
        
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def parse_entries_html(html_content, track_code, race_date):
    """
    Parse the Equibase Entries HTML page
    Returns list of races with entries
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    races = []
    
    # Try finding headers like "Race X"
    race_headers = soup.find_all(string=re.compile(r'Race\s+\d+', re.IGNORECASE))
    
    processed_race_nums = set()

    for header in race_headers:
        try:
            header_text = header.strip()
            # Check if this is a header we care about
            match = re.search(r'Race\s+(\d+)', header_text, re.IGNORECASE)
            if not match:
                continue
                
            race_num = int(match.group(1))
            # logger.info(f"Processing Header: {header_text[:20]}... Race {race_num}")
            if race_num in processed_race_nums:
                # logger.info(f"Skipping Race {race_num}, already processed")
                continue
                
            # Now try to extract race details relative to this header
            container = header.find_parent('table') 
            if not container:
                container = header.find_parent('div')
            
            # Static page fallback: header might be in a div, but table is in parent's sibling or parent's parent
            if not container:
                continue
                
            # Extract Post Time
            post_time = None
            pt_match = re.search(r'Post\s*Time.*?(\d{1,2}:\d{2}\s*(?:AM|PM)?)', container.get_text(), re.IGNORECASE)
            if pt_match:
                post_time = pt_match.group(1)
            
            # Extract Distance
            distance = None
            dist_match = re.search(r'(\d+\s*(?:Furlongs?|Miles?|Yards?))', container.get_text(), re.IGNORECASE)
            if dist_match:
                distance = dist_match.group(1)
                
            # Extract Surface
            surface = 'Dirt' # default
            if 'Turf' in container.get_text():
                surface = 'Turf'
            elif 'All Weather' in container.get_text() or 'Synthetic' in container.get_text():
                surface = 'Synthetic'
                
            # Extract Purse
            purse = None
            purse_match = re.search(r'Purse[:\s]+\$(\d{1,3}(?:,\d{3})*)', container.get_text(), re.IGNORECASE)
            if purse_match:
                purse = f"${purse_match.group(1)}"
            
            # Find the entries table
            entries = []
            entry_table = None
            
            def is_entry_table(t):
                txt = t.get_text()
                return 'Program' in txt or 'Pgm' in txt or 'Horse' in txt or 'P#' in txt

            tables_in_container = container.find_all('table')
            
            # If no tables in header's container, check the PARENT container (likely for static pages)
            if not tables_in_container:
                logger.info(f"Race {race_num}: No tables in header container, checking parent...") # Debug
                if container.parent:
                    container = container.parent
                    tables_in_container = container.find_all('table')

            for tbl in tables_in_container:
                if is_entry_table(tbl):
                    entry_table = tbl
                    break
            
            if not entry_table:
                # Try siblings of the container
                curr = container
                for _ in range(5): 
                    curr = curr.find_next_sibling()
                    if curr:
                        if curr.name == 'table' and is_entry_table(curr):
                            entry_table = curr
                            break
                        # Check tables inside the sibling div/etc
                        elif curr.name == 'div':
                            sub_tables = curr.find_all('table')
                            for st in sub_tables:
                                if is_entry_table(st):
                                    entry_table = st
                                    break
                        if entry_table: break
            
            if entry_table:
                # Parse Rows
                rows = entry_table.find_all('tr')
                # Skip header
                start_row = 1 
                
                for row in rows[start_row:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 5:
                        continue
                        
                    try:
                        # Clean text
                        col_texts = [c.get_text(strip=True) for c in cols]
                        
                        pgm = col_texts[0]
                        horse_name = col_texts[1]
                        
                        # Remove (L) etc from horse name
                        horse_name = re.sub(r'\s*\(.*?\)', '', horse_name).strip()
                        
                        jockey = col_texts[2] if len(col_texts) > 2 else None
                        trainer = col_texts[4] if len(col_texts) > 4 else None
                        odds_ml = col_texts[5] if len(col_texts) > 5 else None
                        
                        # Validate Pgm is a number (or like 1A)
                        if not re.match(r'^\d', pgm):
                            continue
                            
                        entries.append({
                            'program_number': pgm,
                            'horse_name': horse_name,
                            'jockey': jockey,
                            'trainer': trainer,
                            'morning_line_odds': odds_ml
                        })
                        
                    except Exception as e:
                        continue
                        
            if entries:
                processed_race_nums.add(race_num)
                races.append({
                    'race_number': race_num,
                    'post_time': post_time,
                    'distance': distance,
                    'surface': surface,
                    'purse': purse,
                    'race_type': 'Unknown', 
                    'entries': entries
                })
                
        except Exception as e:
            logger.error(f"Error parsing race section: {e}")
            continue
            
    return races

def insert_upcoming_race(supabase, track_code, race_date, race_data):
    """
    Insert upcoming race into DB
    CRITICAL: Do NOT overwrite if race exists and is 'completed'
    """
    try:
        # Get track ID
        track_id = get_or_create_track(supabase, track_code)
        if not track_id:
            return False
            
        race_num = race_data['race_number']
        race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{race_num}"
        
        # Check existing
        existing = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key).execute()
        
        race_id = None
        
        if existing.data:
            rec = existing.data[0]
            if rec['race_status'] == 'completed':
                logger.info(f"Skipping {race_key} (already completed)")
                return True
            else:
                race_id = rec['id']
                # Update info if needed (e.g. changes)
        
        # Prepare Race Object
        race_obj = {
            'race_key': race_key,
            'track_id': track_id,
            'track_code': track_code,
            'race_date': race_date.strftime('%Y-%m-%d'),
            'race_number': race_num,
            'race_status': 'upcoming',
            'data_source': 'equibase_entries',
            # 'post_time': race_data.get('post_time'), # Handle conditionally
            'distance': race_data.get('distance'),
            'surface': race_data.get('surface'),
            'purse': race_data.get('purse')
        }

        # Only include post_time in update if it is NOT None
        # Use explicit None check so we don't skip actual data
        if race_data.get('post_time'):
            race_obj['post_time'] = race_data.get('post_time')
        
        if race_id:
            supabase.table('hranalyzer_races').update(race_obj).eq('id', race_id).execute()
        else:
            res = supabase.table('hranalyzer_races').insert(race_obj).execute()
            if res.data:
                race_id = res.data[0]['id']
                
        if not race_id:
            return False
            
        # Insert Entries
        for entry in race_data['entries']:
            # Get/Create Horse
            horse_name = entry['horse_name']
            if not horse_name: continue
            
            # Simple horse get/create (re-use logic or direct)
            h_res = supabase.table('hranalyzer_horses').select('id').eq('horse_name', horse_name).execute()
            if h_res.data:
                horse_id = h_res.data[0]['id']
            else:
                h_new = supabase.table('hranalyzer_horses').insert({'horse_name': horse_name}).execute()
                horse_id = h_new.data[0]['id'] if h_new.data else None
                
            if not horse_id: continue
            
            # Jockey / Trainer
            jockey_id = get_or_create_participant(supabase, 'hranalyzer_jockeys', 'jockey_name', entry.get('jockey')) if entry.get('jockey') else None
            trainer_id = get_or_create_participant(supabase, 'hranalyzer_trainers', 'trainer_name', entry.get('trainer')) if entry.get('trainer') else None
            
            entry_obj = {
                'race_id': race_id,
                'horse_id': horse_id,
                'program_number': entry.get('program_number'),
                'jockey_id': jockey_id,
                'trainer_id': trainer_id,
                'morning_line_odds': entry.get('morning_line_odds')
            }
            
            # Upsert entry
            supabase.table('hranalyzer_race_entries').upsert(entry_obj, on_conflict='race_id, program_number').execute()
            
        return True
        
    except Exception as e:
        logger.error(f"Error inserting upcoming race {race_key}: {e}")
        return False

def crawl_entries(target_date=None, tracks=None):
    """Main function to crawl entries"""
    if not target_date:
        target_date = date.today()
    if not tracks:
        tracks = COMMON_TRACKS
        
    logger.info(f"Crawling entries for {target_date}")
    supabase = get_supabase_client()
    
    stats = {'races_found': 0, 'races_inserted': 0}
    
    driver = None
    try:
        logger.info("Starting Selenium Driver...")
        driver = get_driver()
        
        # 1. Start at Homepage with Retry Logic
        url = "https://www.equibase.com"
        success = False
        
        for attempt in range(3):
            try:
                logger.info(f"Navigating to Homepage {url} (Attempt {attempt+1}/3)")
                driver.get(url)
                time.sleep(5)
                
                title = driver.title
                logger.info(f"Home Title: {title}")
                
                if title and "Just a moment" not in title and title.strip() != "":
                    success = True
                    break
                else:
                    logger.warning("Blocked or Empty Page. Retrying...")
                    time.sleep(10)
            except Exception as e:
                logger.error(f"Nav Error: {e}")
                
        if not success:
            logger.error("Failed to load Homepage after 3 attempts.")
            # Try direct fallback as last resort
            driver.get("https://www.equibase.com/static/entry/index.html")
        else:
            try:
                # Handle potential "Unic Modal" / Privacy popup
                try:
                    logger.info("Checking for blocking modals...")
                    driver.execute_script("""
                        var modals = document.querySelectorAll('.unic-modal');
                        modals.forEach(m => m.remove());
                        var backdrops = document.querySelectorAll('.unic-backdrop');
                        backdrops.forEach(b => b.remove());
                    """)
                    time.sleep(1)
                except:
                    pass

                # Click "Entries" from nav
                logger.info("Looking for 'Entries' link...")
                # Mobile menu might hide it? PROBE LINKS if mobile
                # On mobile, Equibase often lists "Entries" directly or in hamburger
                # Let's search for ANY link containing 'Entries'
                
                links = driver.find_elements(By.TAG_NAME, "a")
                entries_link = None
                for l in links:
                    href = l.get_attribute("href")
                    if "entries" in l.text.lower() or (href and "entries" in href) or "Entries" in l.text:
                         if l.is_displayed():
                             entries_link = l
                             break
                
                if entries_link:
                    logger.info(f"Clicking Entries link: {entries_link.text}")
                    driver.execute_script("arguments[0].click();", entries_link)
                    time.sleep(5)
                else:
                    logger.warning("Could not find visible Entries link. Using direct static URL.")
                    driver.get("https://www.equibase.com/static/entry/index.html")
                    time.sleep(5)
                
            except Exception as e:
                logger.warning(f"Nav Error: {e}")
                driver.get("https://www.equibase.com/static/entry/index.html")

        logger.info(f"Current Page Title: {driver.title}")
        logger.info(f"Current URL: {driver.current_url}")
        
        # Map track_code -> url
        valid_urls = {}
        
        target_day = str(target_date.day)
        logger.info(f"Looking for links with text '{target_day}' for date {target_date}")
        
        # DEBUG: Dump all rows to see what we are working with
        rows = driver.find_elements(By.TAG_NAME, "tr")
        logger.info(f"Found {len(rows)} rows in page")
        
        track_name_map = {
            'GP': 'Gulfstream Park',
            'AQU': 'Aqueduct',
            'FG': 'Fair Grounds',
            'SA': 'Santa Anita',
            'TAM': 'Tampa Bay',
            'OP': 'Oaklawn Park',
            'PRX': 'Parx Racing',
            'LRL': 'Laurel Park',
            'TP': 'Turfway Park',
            'MVR': 'Mahoning Valley',
            'CT': 'Charles Town',
            'PEN': 'Penn National',
            'DED': 'Delta Downs',
            'HOU': 'Sam Houston',
            'TUP': 'Turf Paradise',
            'GG': 'Golden Gate',
            'WO': 'Woodbine'
        }

        for row in rows:
            try:
                row_text = row.text
                if not row_text.strip(): continue
                
                # Check if this row is for one of our tracks
                found_track = None
                for t_code, t_name in track_name_map.items():
                    if t_name in row_text:
                        found_track = (t_code, t_name)
                        break
                
                if found_track:
                    track_code, track_name = found_track
                    logger.info(f"ROW MATCH [{track_code}]: {row_text[:50]}...")
                    
                    # Find links in this row
                    links = row.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        link_text = link.text.strip()
                        link_href = link.get_attribute('href')
                        
                        # Match logic for Static Page:
                        # Link text is just the day number (e.g. "13")
                        # OR if regex match for date
                        
                        is_match = False
                        if link_text == target_day:
                            is_match = True
                        elif f"/{track_code}{target_date.strftime('%m%d')}" in (link_href or ""):
                             # Fallback: check if href contains track + MMDD (ignoring year/suffix)
                             is_match = True

                        if is_match and link_href:
                            logger.info(f"    !!! MATCH FOUND for {track_code} !!!")
                            valid_urls[track_code] = link_href
                            break # Found the link for this track
                            
            except Exception as e:
                pass # Stale element etc

        # Fallback loop to just log what's missing
        for track_code in tracks:
            if track_code not in valid_urls:
                logger.info(f"No URL resolved for {track_code}")

        # 2. Crawl the found URLs
        for track_code, url in valid_urls.items():
            logger.info(f"Fetching {url}")
            
            try:
                driver.get(url)
                # Wait for potential challenge or content
                time.sleep(3) 
                
                content = driver.page_source
                
                # Basic verification
                if "Pardon Our Interruption" in driver.title:
                    logger.warning(f"Access Denied for {track_code}. Retrying...")
                    time.sleep(5)
                    driver.get(url) 
                    time.sleep(5)
                    content = driver.page_source
                
                races = parse_entries_html(content, track_code, target_date)
                if races:
                    logger.info(f"Found {len(races)} races for {track_code}")
                    stats['races_found'] += len(races)
                    
                    for race in races:
                        if insert_upcoming_race(supabase, track_code, target_date, race):
                            stats['races_inserted'] += 1
                else:
                    logger.info(f"No parseable races found for {track_code}")
                
                time.sleep(2) 
                
            except Exception as e:
                logger.error(f"Error processing {track_code}: {e}")
                
    except Exception as e:
        logger.error(f"Selenium Driver Init failed: {e}")
    finally:
        if driver:
            driver.quit()
            
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl_entries()
