"""
Crawl Equibase Entries (Upcoming Races)
Parses HTML from Equibase to get upcoming race data
Uses requests to fetch static pages (bypassing WAF/Selenium instability)
"""
import requests
import re
import logging
import time
import os
from datetime import datetime, date
from bs4 import BeautifulSoup
import subprocess

from supabase_client import get_supabase_client
from crawl_equibase import get_or_create_track, get_or_create_participant, normalize_pgm, COMMON_TRACKS

logger = logging.getLogger(__name__)

# Map Equibase codes to HRN slugs
HRN_TRACK_MAP = {
    'GP': 'gulfstream-park',
    'AQU': 'aqueduct',
    'FG': 'fair-grounds',
    'SA': 'santa-anita',
    'TAM': 'tampa-bay-downs',
    'OP': 'oaklawn-park',
    'PRX': 'parx-racing',
    'LRL': 'laurel-park',
    'TP': 'turfway-park',
    'MVR': 'mahoning-valley', 
    'CT': 'charles-town',
    'PEN': 'penn-national',
    'DED': 'delta-downs',
    'HOU': 'sam-houston-race-park',
    'TUP': 'turf-paradise',
    'GG': 'golden-gate-fields',
    'WO': 'woodbine'
}

def get_static_entry_url(track_code, race_date):
    """
    Construct the static URL for a track's entries
    Format: https://www.equibase.com/static/entry/{CODE}{MM}{DD}{YY}USA-EQB.html
    """
    mm = race_date.strftime('%m')
    dd = race_date.strftime('%d')
    yy = race_date.strftime('%y')
    
    # Standard format
    url = f"https://www.equibase.com/static/entry/{track_code}{mm}{dd}{yy}USA-EQB.html"
    return url

def fetch_static_page(url, retries=3):
    """
    Fetch static page using PowerShell (Bypassing WAF)
    Requests/Curl with specific headers failed. PowerShell IWR works.
    """
    temp_file = f"temp_entry_{int(time.time())}.html"
    
    for attempt in range(retries):
        try:
            logger.info(f"Fetching {url} via PowerShell (Attempt {attempt+1})")
            
            # Using default UserAgent of PowerShell 5.1/7 seems to work
            cmd = ["powershell", "-Command", f"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_file}'"]
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                size = os.path.getsize(temp_file)
                if size < 5000:
                    logger.warning(f"Downloaded file too small ({size} bytes). Likely blocked.")
                    # If blocked, maybe try waiting or retry
                else:
                    # Success
                    with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Cleanup
                    try: os.remove(temp_file) 
                    except: pass
                    
                    return content
            else:
                 logger.warning(f"PowerShell failed: {result.stderr}")
                 
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            time.sleep(2)
            
    # Cleanup if failed
    if os.path.exists(temp_file):
        try: os.remove(temp_file)
        except: pass
        
    return None

def parse_entries_html(html_content, track_code, race_date):
    """
    Parse the Equibase Entries HTML page (Static Version)
    Returns list of races with entries
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    races = []
    
    # 1. Find all Race containers (div id="Race1", "Race2", etc.)
    # In static pages, they are often <div id="RaceX"> ... </div>
    race_divs = soup.find_all('div', id=re.compile(r'^Race\d+$'))
    
    # logger.info(f"Found {len(race_divs)} race divs in static content")
    
    for race_div in race_divs:
        try:
            # Race Number from ID
            race_id_str = race_div.get('id')
            if not race_id_str: continue
            
            # id="Race4"
            race_number_match = re.search(r'Race(\d+)', race_id_str)
            if not race_number_match:
                continue
            race_num = int(race_number_match.group(1))
            
            # --- Header Info ---
            race_info = race_div.find('div', class_='race-info')
            if not race_info:
                # Sometimes race-info is not direct child?
                race_info = race_div.find('div', class_=lambda x: x and 'race-info' in x)
            
            post_time = None
            distance_text = None
            surface_text = 'Dirt' # default
            purse_text = None
            race_type_text = None
            
            if race_info:
                # Race Type
                rt_h3 = race_info.find('h3')
                if rt_h3:
                    race_type_text = rt_h3.get_text(strip=True)

                # Details Line
                h5 = race_info.find('h5')
                if h5:
                    full_text = h5.get_text(" | ", strip=True) 
                    parts = [p.strip() for p in full_text.split('|') if p.strip() and p.strip() != '.']
                    
                    for part in parts:
                        # Post Time
                        if "PM" in part or "AM" in part:
                            # 1:26 PM ET
                            tm_match = re.search(r'(\d{1,2}:\d{2}\s+(?:AM|PM))', part, re.IGNORECASE)
                            if tm_match:
                                post_time = tm_match.group(1)
                        
                        # Distance
                        elif any(x in part.upper() for x in [' F', ' Y', 'MILE', 'FURLONG']):
                             distance_text = part
                        
                        # Purse
                        elif part.startswith('$'):
                            purse_text = part
                            
                        # Surface
                        elif part.lower() in ['dirt', 'turf', 'all weather', 'synthetic', 'outer turf', 'inner turf']:
                            surface_text = part
            
            # --- Entries ---
            entries = []
            
            # Strategy: specific divs ".contenders .row" seems most reliable for mobile/static views
            content_div = race_div.find('div', class_='content')
            contenders_div = race_div.find('div', class_='contenders')
            
            if contenders_div:
                for row in contenders_div.find_all('div', class_='row'):
                    # Check for saddlecloth
                    saddle_div = row.find('div', class_=lambda x: x and 'saddlecloth' in x)
                    if not saddle_div: continue
                    
                    pgm = saddle_div.get_text(strip=True)
                    
                    # Horse: h4 > b > a (or just h4 > a)
                    horse_name = "Unknown"
                    h4 = row.find('h4')
                    if h4:
                        a_tag = h4.find('a')
                        if a_tag:
                            horse_name = a_tag.get_text(strip=True)
                    
                    # Clean horse name
                    horse_name = re.sub(r'\s*\(.*?\)', '', horse_name).strip()
                    
                    # Jockey
                    jockey = None
                    mj = row.find(string=re.compile(r'Jockey:', re.IGNORECASE))
                    if mj and mj.find_parent('div'):
                        a_j = mj.find_parent('div').find('a')
                        if a_j: jockey = a_j.get_text(strip=True)

                    # Trainer
                    trainer = None
                    mt = row.find(string=re.compile(r'Trainer:', re.IGNORECASE))
                    if mt and mt.find_parent('div'):
                         a_t = mt.find_parent('div').find('a')
                         if a_t: trainer = a_t.get_text(strip=True)
                            
                    # Odds
                    odds_ml = None
                    mo = row.find(string=re.compile(r'M/L Odds:', re.IGNORECASE)) 
                    if mo:
                        full_line = mo.parent.get_text() 
                        omask = re.search(r'M/L Odds:\s*([\d/]+|[\d\.]+)', full_line)
                        if omask:
                            odds_ml = omask.group(1)
                    
                    entries.append({
                        'program_number': pgm,
                        'horse_name': horse_name,
                        'jockey': jockey,
                        'trainer': trainer,
                        'morning_line_odds': odds_ml,
                        'scratched': False
                    })

                    # Check for scratch indications
                    # 1. "SCR" in odds
                    # 2. "SCR" or "Scratched" in Program Number (sometimes happens)
                    # 3. "Scratched" in horse name bucket
                    
                    # Logic
                    is_scratch = False
                    if odds_ml and 'SCR' in odds_ml.upper():
                        is_scratch = True
                    elif pgm and 'SCR' in pgm.upper():
                        is_scratch = True
                    
                    if is_scratch:
                        entries[-1]['scratched'] = True
                        entries[-1]['morning_line_odds'] = 'SCR'  # Normalize
                        if not entries[-1]['program_number'] or entries[-1]['program_number'] == '0':
                             entries[-1]['program_number'] = 'SCR'
            else:
                 # Fallback to standard table parsing if Contenders div is missing
                 # (Some tracks might use table view in static)
                 tables = race_div.find_all('table')
                 for tbl in tables:
                     if 'saddlecloth' in str(tbl).lower():
                         rows_t = tbl.find_all('tr')
                         for row_t in rows_t:
                             cols = row_t.find_all('td')
                             if len(cols) < 3: continue
                             
                             pgm_div = row_t.find('div', class_=lambda x: x and 'paddingSaddleCloths' in x)
                             if not pgm_div: continue
                             pgm = pgm_div.get_text(strip=True)
                             
                             h_link = row_t.find('a', href=re.compile(r'type=Horse'))
                             h_name = h_link.get_text(strip=True) if h_link else "Unknown"
                             h_name = re.sub(r'\s*\(.*?\)', '', h_name).strip()
                             
                             j_link = row_t.find('a', href=re.compile(r'searchType=J'))
                             j_name = j_link.get_text(strip=True) if j_link else None
                             
                             t_link = row_t.find('a', href=re.compile(r'searchType=T'))
                             t_name = t_link.get_text(strip=True) if t_link else None
                             
                             o_ml = None
                             for col in cols:
                                 if re.match(r'^\d+/\d+$', col.get_text(strip=True)):
                                     o_ml = col.get_text(strip=True)
                                     break
                                     
                             entries.append({
                                'program_number': pgm,
                                'horse_name': h_name,
                                'jockey': j_name,
                                'trainer': t_name,
                                'morning_line_odds': o_ml
                            })
                         break

            if entries:
                 # Clean Purse string
                 if purse_text:
                     purse_text = re.sub(r'[^\d]', '', purse_text) 
                     if purse_text: purse_text = f"${purse_text}"

                 races.append({
                    'race_number': race_num,
                    'post_time': post_time,
                    'distance': distance_text,
                    'surface': surface_text,
                    'purse': purse_text,
                    'race_type': race_type_text,
                    'entries': entries
                 })
                 
        except Exception as e:
            logger.error(f"Error parsing race div {race_div.get('id')}: {e}")
            continue
            
    return races

def fetch_hrn_entries(track_code, race_date):
    """
    Fallback: Fetch entries from HorseRacingNation
    """
    slug = HRN_TRACK_MAP.get(track_code)
    if not slug:
        return []
        
    url = f"https://entries.horseracingnation.com/entries-results/{slug}/{race_date.strftime('%Y-%m-%d')}"
    logger.info(f"Fallback: Fetching HRN {url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=20)
        
        if r.status_code != 200:
            logger.warning(f"HRN status {r.status_code}")
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        races = []
        
        all_tables = soup.find_all('table')
        if not all_tables:
            return []
            
        # Filter for tables that are actually entry tables
        entry_tables = []
        for table in all_tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            # Look for indicators of an entry table
            # Match count strategy to avoid generic tables (like 'Power Picks') which only have 'Horse'
            # We need at least 2 matches from the entry-specific columns
            matches = sum(1 for h in headers if any(k in h for k in ['#', 'pp', 'horse', 'ml', 'jockey', 'trainer', 'morning']))
            
            if matches >= 2:
                entry_tables.append(table)
        
        if not entry_tables:
            logger.info("No entry tables found on HRN page.")
            return []
            
        for idx, table in enumerate(entry_tables):
            race_num = idx + 1
            entries = []
            
            # Extract header info (Post Time, Purse, etc)
            post_time = None
            distance = None
            surface = None
            purse = None
            race_type = None
            
            # 1. NEW: TRY CLASS-BASED DETECTION (RESULTS PAGE)
            # Find the header element for this race
            header_div = soup.find(id=f"race-{race_num}")
            if header_div:
                # Post Time
                pt_tag = header_div.find('time', class_='race-time')
                if pt_tag:
                    post_time = pt_tag.get_text(strip=True)
                
                # Metadata (Purse, Dist)
                # It's usually in a row following the parent h2
                parent_h2 = header_div.find_parent('h2')
                if parent_h2:
                    details_row = parent_h2.find_next_sibling('div', class_='row')
                    if details_row:
                        # Purse
                        purse_tag = details_row.find(class_='race-purse')
                        if purse_tag:
                            purse = purse_tag.get_text(strip=True).replace('Purse:', '').strip()
                        
                            # Improved Parsing Logic for HRN
                            dist_tag = details_row.find(class_='race-distance')
                            if dist_tag:
                                # Use pipe to separate text nodes if possible, but get_text might not be perfect.
                                text_content = dist_tag.get_text("|", strip=True) 
                            # "6 f|Dirt|$15,000 Claiming"
                            
                            raw_parts = [p.strip() for p in text_content.split('|') if p.strip()]
                            
                            final_parts = []
                            for p in raw_parts:
                                clean_p = " ".join(p.split())
                                # Split by comma but be smart about currency
                                sub_parts = [sp.strip() for sp in clean_p.split(',')]
                                for sp in sub_parts:
                                    if not sp: continue
                                    # Merge currency split (e.g. $5 and 000)
                                    if final_parts and re.match(r'^\$\d{1,3}$', final_parts[-1]) and re.match(r'^\d{3}', sp):
                                        final_parts[-1] += "," + sp
                                    else:
                                        final_parts.append(sp)

                            # Parse final_parts
                            for part in final_parts:
                                part_lower = part.lower()
                                
                                # Distance Check: starts with digit, contains specific unit (relaxed regex)
                                if not distance and re.match(r'^\d', part) and re.search(r'(m|f|y|mile|furlong|yds)', part_lower):
                                     distance = part
                                
                                # Surface Check
                                elif not surface and any(x in part_lower for x in ['dirt', 'turf', 'synthetic', 'all weather']):
                                     surface = part
                                     
                                # Race Type: Not distance, not surface, not 'purse'
                                else:
                                     if 'purse:' in part_lower:
                                         continue
                                     # Append to race type (handles multi-part types if any)
                                     if not race_type:
                                         race_type = part
                                     else:
                                         race_type += f" {part}"


            # 2. FALLBACK: SIBLING SEARCH (ENTRY PAGE)
            if not post_time or not distance:
                prev = table.find_previous_sibling()
                for _ in range(5):
                    if not prev: break
                    txt = prev.get_text(" ", strip=True)
                    
                    # Check Post Time (e.g. "Post time: 12:10 PM ET")
                    if not post_time:
                        # try strict first
                        pt_match = re.search(r'(?:Post time:)?\s*(\d{1,2}:\d{2}\s*(?:AM|PM))', txt, re.IGNORECASE)
                        if pt_match:
                            post_time = pt_match.group(1)
                        else:
                            # Try flexible: "12:30 PM" without prefix, or "1:00" if clear
                            pt_strict = re.search(r'\b(\d{1,2}:\d{2}\s*(?:A\.?M\.?|P\.?M\.?))', txt, re.IGNORECASE)
                            if pt_strict:
                                post_time = pt_strict.group(1)

                    # Distance
                    if not distance:
                        dist_match = re.search(r'(\d+(?:\.\d+)?\s*(?:f|furlongs|miles|yards|yds))', txt, re.IGNORECASE)
                        if dist_match: distance = dist_match.group(1)
                    
                    # Surface
                    if not surface:
                        surf_match = re.search(r'(Dirt|Turf|Synthetic|All Weather|Inner Turf|Main Track)', txt, re.IGNORECASE)
                        if surf_match: surface = surf_match.group(1)
                    
                    # Purse
                    if not purse:
                        purse_match = re.search(r'Purse\s*[:\s]*(\$\d{1,3}(?:,\d{3})*)', txt, re.IGNORECASE)
                        if purse_match:
                            purse = purse_match.group(1)
                        elif '$' in txt:
                            # Look for isolated currency like $15,000
                            pm = re.search(r'(\$\d{1,3}(?:,\d{3})+(?:\.\d{2})?)', txt)
                            if pm: purse = pm.group(1)
                            
                    prev = prev.find_previous_sibling()

            # Parse Rows
            rows = table.find_all('tr')
            # Check header row
            if not rows: continue
            
            # Identify columns
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            # Expected: ['#', 'pp', 'horse', 'trainer / jockey', 'ml']
            
            # Map columns
            idx_pgm = -1
            idx_pp = -1
            idx_horse = -1
            idx_tj = -1
            idx_ml = -1
            
            for i, h in enumerate(headers):
                if '#' in h: idx_pgm = i
                elif 'pp' in h: idx_pp = i
                elif 'horse' in h: idx_horse = i
                elif 'trainer' in h or 'jockey' in h: idx_tj = i
                elif 'ml' in h: idx_ml = i
            
            # Fallback indices if header detection fails
            if idx_pgm == -1: idx_pgm = 0
            if idx_horse == -1: idx_horse = 2
            if idx_tj == -1: idx_tj = 3
            if idx_ml == -1: idx_ml = 4
            
            for row in rows:
                cols = row.find_all('td')
                if not cols: continue # header
                
                try:
                    pgm = cols[idx_pgm].get_text(strip=True) if (idx_pgm != -1 and len(cols) > idx_pgm) else ""
                    
                    # Fallback to PP if PGM is empty
                    if not pgm and idx_pp != -1 and len(cols) > idx_pp:
                         pgm = cols[idx_pp].get_text(strip=True)
                         
                    if not pgm: pgm = "0"
                    
                    # Horse Name 
                    horse_part = cols[idx_horse] if len(cols) > idx_horse else None
                    horse_name = horse_part.get_text(strip=True) if horse_part else "Unknown"
                    # HRN puts sire info in same cell usually? 2 | Horse Name | (Sire) ...
                    # Let's clean it up.
                    # Usually "Horse Name\n(Score)\nSire"
                    # Just take first line or bold part?
                    if horse_part and horse_part.find('strong'): # bold name
                         horse_name = horse_part.find('strong').get_text(strip=True)
                    elif horse_part and horse_part.find('a'):
                         horse_name = horse_part.find('a').get_text(strip=True)
                    else:
                         horse_name = horse_name.split('|')[0].strip()

                    # Trainer / Jockey
                    tj_part = cols[idx_tj] if len(cols) > idx_tj else None
                    trainer = None
                    jockey = None
                    if tj_part:
                        # "Trainer Name | Jockey Name"
                        txt = tj_part.get_text("|", strip=True) 
                        parts = txt.split('|')
                        if len(parts) >= 1: trainer = parts[0].strip()
                        if len(parts) >= 2: jockey = parts[1].strip()
                        
                    # Odds
                    odds = cols[idx_ml].get_text(strip=True) if (idx_ml != -1 and len(cols) > idx_ml) else None
                    
                    entries.append({
                        'program_number': pgm,
                        'horse_name': horse_name,
                        'jockey': jockey,
                        'trainer': trainer,
                        'morning_line_odds': odds
                    })
                except:
                    continue
            
            if entries:
                races.append({
                    'race_number': race_num,
                    'post_time': post_time,
                    'distance': distance,
                    'surface': surface,
                    'purse': purse,
                    'race_type': race_type if race_type else 'Unknown',
                    'entries': entries,
                    'source': 'hrn_entries'
                })
                
        return races

    except Exception as e:
        logger.error(f"HRN Fetch Error: {e}")
        return []

def insert_upcoming_race(supabase, track_code, race_date, race_data, allow_completed_update=False):
    """
    Insert upcoming race into DB
    CRITICAL: By default, do NOT overwrite if race exists and is 'completed'
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
        current_status = None
        
        if existing.data:
            rec = existing.data[0]
            current_status = rec['race_status']
            if current_status == 'completed' and not allow_completed_update:
                logger.info(f"Skipping {race_key} (already completed)")
                return True
            else:
                race_id = rec['id']
                # Update info if needed (e.g. changes)
        
        # Prepare Race Object with only non-None values to avoid overwriting existing data
        race_obj = {
            'race_key': race_key,
            'track_id': track_id,
            'track_code': track_code,
            'race_date': race_date.strftime('%Y-%m-%d'),
            'race_number': race_num
        }
        
        # Preserve status if updating, otherwise default to 'upcoming'
        if not race_id:
            race_obj['race_status'] = 'upcoming'
        elif current_status:
            race_obj['race_status'] = current_status
        
        if race_data.get('source'):
            race_obj['data_source'] = race_data['source']
        else:
            race_obj['data_source'] = 'entries_crawler'

        # Optional fields
        for field in ['distance', 'surface', 'purse', 'post_time', 'race_type']:
            if race_data.get(field):
                race_obj[field] = race_data[field]
        
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
            
            pgm_val = entry.get('program_number', '0')
            if pgm_val:
                pgm_val = str(pgm_val)[:10]
                
            entry_obj = {
                'race_id': race_id,
                'horse_id': horse_id,
                'program_number': normalize_pgm(pgm_val),
                'jockey_id': jockey_id,
                'trainer_id': trainer_id,
                'trainer_id': trainer_id,
                'morning_line_odds': entry.get('morning_line_odds'),
                'scratched': entry.get('scratched', False)
            }
            
            # Upsert entry
            supabase.table('hranalyzer_race_entries').upsert(entry_obj, on_conflict='race_id, program_number').execute()
            
        return True
        
    except Exception as e:
        logger.error(f"Error inserting upcoming race {race_key}: {e}")
        return False

def crawl_entries(target_date=None, tracks=None, allow_completed_update=False):
    """Main function to crawl entries using Static Pages (HRN Primary, Equibase Fallback)"""
    if not target_date:
        target_date = date.today()
    if not tracks:
        tracks = COMMON_TRACKS
        
    logger.info(f"Crawling entries for {target_date}")
    supabase = get_supabase_client()
    
    stats = {'races_found': 0, 'races_inserted': 0}
    
    for track_code in tracks:
        try:
            # 1. TRY HRN PRIMARY
            races = fetch_hrn_entries(track_code, target_date)
            
            if not races:
                logger.info(f"HRN empty/failed for {track_code}. Trying Fallback (Equibase)...")
                # 2. TRY EQUIBASE FALLBACK
                url = get_static_entry_url(track_code, target_date)
                html = fetch_static_page(url)
                if html:
                    races = parse_entries_html(html, track_code, target_date)
            
            if races:
                logger.info(f"Found {len(races)} races for {track_code}")
                stats['races_found'] += len(races)
                
                for race in races:
                    if insert_upcoming_race(supabase, track_code, target_date, race, allow_completed_update=allow_completed_update):
                        stats['races_inserted'] += 1
            else:
                logger.info(f"All sources empty for {track_code}")
                
            
            # Sleep slightly to be polite to HRN/Equibase
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Error processing {track_code}: {e}")
            time.sleep(10)
            
    logger.info(f"Entries Crawl Complete. Stats: {stats}")
    return stats

if __name__ == "__main__":
    # Robust logging setup
    backend_dir = os.path.dirname(__file__)
    log_file = os.path.join(backend_dir, 'crawler.log')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers if any
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    
    logger.info(f"--- Crawler Manual Run Started: {datetime.now()} ---")
    
    crawl_entries()
