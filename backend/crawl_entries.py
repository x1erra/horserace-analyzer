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
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Try to find chromium executable if on Pi/Linux
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        
    driver = webdriver.Chrome(options=options)
    return driver

def get_entries_url(track_code, race_date):
    """
    Construct Equibase Entries URL
    Format: https://www.equibase.com/static/entry/GP011126USA-EQB.html
    """
    date_str = race_date.strftime('%m%d%y')
    return f"https://www.equibase.com/static/entry/{track_code}{date_str}USA-EQB.html"

def parse_entries_html(html_content, track_code, race_date):
    """
    Parse the Equibase Entries HTML page
    Returns list of races with entries
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    races = []
    
    # Equibase entries pages usually list multiple races
    # They often use anchor tags like <a name="race1"></a>
    
    # Implementation strategy:
    # 1. Find all race tables or sections
    # 2. Extract Race Number, Post Time, Distance, Surface, Conditions
    # 3. Extract Horses table
    
    # This is a bit tricky because the layout isn't always semantic tables
    # But usually "Race 1 - ..." is a header
    
    # Try finding headers like "Race X"
    race_headers = soup.find_all(string=re.compile(r'Race\s+\d+', re.IGNORECASE))
    
    processed_race_nums = set()

    for header in race_headers:
        try:
            # Navigate up to find the container
            # Header text is usually in a <strong> or <span> or just text node
            # Example: "Race 1 - Post Time ..." or just "Race 1"
            
            header_text = header.strip()
            # Check if this is a header we care about
            match = re.search(r'Race\s+(\d+)', header_text, re.IGNORECASE)
            if not match:
                continue
                
            race_num = int(match.group(1))
            if race_num in processed_race_nums:
                continue
                
            # Now try to extract race details relative to this header
            # We look for the "next" table which should be the participants
            
            # Context search: limit scope
            container = header.find_parent('table') # Usually race header is inside a table or div
            if not container:
                container = header.find_parent('div')
            
            if not container:
                continue
                
            # Extract Post Time
            # Often in text "Post Time: 12:10 PM"
            post_time = None
            pt_match = re.search(r'Post Time[:\s]+(\d{1,2}:\d{2}\s*(?:AM|PM)?)', container.get_text(), re.IGNORECASE)
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
            # It usually follows the header container
            # Look for table with "Program" or "Pgm" in header
            
            # Important: find the MAIN container for the WHOLE PAGE content if possible to iterate linearly
            # Alternative: find next table sibling
            
            entries = []
            
            # Go down the DOM or next siblings to find the table
            # Sometimes the header is IN the table row 1
            
            entry_table = None
            # Heuristic: Find all tables, check if they are "near" the header
            # OR check if container IS the table
            
            tables_in_container = container.find_all('table')
            for tbl in tables_in_container:
                if 'Program' in tbl.get_text() or 'Pgm' in tbl.get_text() or 'Horse' in tbl.get_text():
                    entry_table = tbl
                    break
            
            # If not in container, look at next siblings of container
            if not entry_table:
                curr = container
                for _ in range(5): # Look ahead 5 siblings
                    curr = curr.find_next_sibling()
                    if curr and curr.name == 'table':
                        if 'Program' in curr.get_text() or 'Pgm' in curr.get_text():
                            entry_table = curr
                            break
            
            if entry_table:
                # Parse Rows
                rows = entry_table.find_all('tr')
                # Skip header
                start_row = 1 
                
                # Check header to map cols? 
                # Doing a naive mapping for now: Pgm, Horse, Jockey, Trainer, Odds
                # Common cols: Pgm, Horse, Jockey, Wgt, Trainer, M/L
                
                for row in rows[start_row:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) < 5:
                        continue
                        
                    try:
                        # Clean text
                        col_texts = [c.get_text(strip=True) for c in cols]
                        
                        # Heuristic col mapping based on typical Equibase layout
                        # Usually: Pgm (0), Horse (1), Jockey (2), Wgt (3), Trainer (4), M/L (5)
                        # Sometimes Horse Name includes meds/equip like "Horse (L)"
                        
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
                    'race_type': 'Unknown', # Hard to parse from header reliably without complexity
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
            'post_time': race_data.get('post_time'),
            'distance': race_data.get('distance'),
            'surface': race_data.get('surface'),
            'purse': race_data.get('purse')
        }
        
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
        
        for track in tracks:
            url = get_entries_url(track, target_date)
            logger.info(f"Fetching {url}")
            
            try:
                driver.get(url)
                # Wait for potential challenge or content
                time.sleep(3) 
                
                # Check for Race Headers which indicates content load
                # Or wait until "Race" text appears
                content = driver.page_source
                
                if "No entries found" in content:
                    logger.info(f"No entries found for {track}")
                    continue
                    
                # Basic verification of load by checking title or critical element
                if "Pardon Our Interruption" in driver.title:
                    logger.warning(f"Access Denied for {track} - WAF block triggered. Retrying...")
                    time.sleep(5)
                    driver.get(url) # Retry once
                    time.sleep(5)
                    content = driver.page_source
                    
                races = parse_entries_html(content, track, target_date)
                if races:
                    logger.info(f"Found {len(races)} races for {track}")
                    stats['races_found'] += len(races)
                    
                    for race in races:
                        if insert_upcoming_race(supabase, track, target_date, race):
                            stats['races_inserted'] += 1
                else:
                    logger.info(f"No parseable races found for {track}")
                    
                time.sleep(2) # Politeness
                
            except Exception as e:
                logger.error(f"Error processing {track}: {e}")
                
    except Exception as e:
        logger.error(f"Selenium Driver Init failed: {e}")
    finally:
        if driver:
            driver.quit()
            
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl_entries()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl_entries()
