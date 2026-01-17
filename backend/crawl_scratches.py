
import logging
import time
import os
import re
import subprocess
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from supabase_client import get_supabase_client
from crawl_equibase import normalize_name, normalize_pgm, COMMON_TRACKS

# Configure logging
logger = logging.getLogger(__name__)

# NOTE: Equibase also provides RSS feeds for late changes which are structured in XML.
# URL: https://www.equibase.com/premium/eqbLateChangeRSS.cfm
# Example Feed: https://www.equibase.com/static/latechanges/rss/AQU-USA.rss
# While structured, the <description> field bundles multiple changes (including cancellations)
# into a single HTML text block that requires regex parsing.
# The current HTML scraper used in this file is preferred for its granular row-based structure,
# but the RSS feed remains a viable "break-glass" fallback if the HTML layout changes drastically.


EQUIBASE_BASE_URL = "https://www.equibase.com/static/latechanges/html/"
LATE_CHANGES_INDEX_URL = "https://www.equibase.com/static/latechanges/html/latechanges.html"

def fetch_static_page(url, retries=3):
    """
    Fetch static page using Python requests library with proper headers.
    Falls back to PowerShell if requests fails.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    for attempt in range(retries):
        try:
            # Try Python requests first
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200 and len(response.text) > 500:
                return response.text
            
            logger.warning(f"Requests got status {response.status_code}, trying PowerShell...")
            
        except requests.exceptions.Timeout:
            logger.warning(f"Requests timeout for {url}, trying PowerShell...")
        except Exception as e:
            logger.warning(f"Requests failed: {e}, trying PowerShell...")
        
        # Fallback to PowerShell
        try:
            temp_file = f"temp_scratches_{int(time.time())}.html"
            cmd = ["powershell", "-Command", f"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_file}' -TimeoutSec 15"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                try: os.remove(temp_file) 
                except: pass
                
                if len(content) > 500:
                    return content
                    
        except Exception as e:
            logger.warning(f"PowerShell fallback failed: {e}")
        finally:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except: pass
        
        time.sleep(1)
        
    logger.error(f"All fetch methods failed for {url}")
    return None

def parse_late_changes_index():
    """
    Parse the main late changes page to find links for specific tracks
    Returns: List of dicts { 'track_code': 'GP', 'url': '...' }
    """
    html = fetch_static_page(LATE_CHANGES_INDEX_URL)
    if not html:
        logger.error("Failed to fetch Late Changes index")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Links are usually in a list or table. 
    # Example href: "latechangesGP-USA.html"
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'latechanges' in href and '-USA.html' in href:
            # Extract track code: latechangesGP-USA.html -> GP
            match = re.search(r'latechanges([A-Z0-9]+)-USA\.html', href)
            if match:
                code = match.group(1)
                full_url = EQUIBASE_BASE_URL + href if not href.startswith('http') else href
                links.append({'track_code': code, 'url': full_url})
                
    return links

def determine_change_type(description):
    """
    Determine the type of change based on the description text
    """
    desc_lower = description.lower()
    
    if 'scratched' in desc_lower:
        return 'Scratch'
    elif 'jockey' in desc_lower:
        return 'Jockey Change'
    elif 'weight' in desc_lower:
        return 'Weight Change'
    elif 'blinker' in desc_lower or 'equipment' in desc_lower:
        return 'Equipment Change'
    elif 'cancel' in desc_lower:
        return 'Race Cancelled'
    
    return 'Other'

def parse_track_changes(html, track_code):
    """
    Parse the changes table for a specific track.
    Captures Scratches, Jockey Changes, and others.
    """
    changes = []
    if not html: return changes
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Table usually has id="fullChanges" or similar, but let's be robust
    tables = soup.find_all('table')
    target_table = None
    
    for t in tables:
        if 'Changes' in t.get_text() or t.find('th', class_='changes'):
            target_table = t
            break
            
    if not target_table:
        return changes
        
    current_race = None
    
    rows = target_table.find_all('tr')
    for row in rows:
        # Check for Race Header
        # <tr class="group-header"><th class="race">Race: 1</th>...</tr>
        header_th = row.find('th', class_='race')
        if header_th:
            txt = header_th.get_text(strip=True)
            # "Race: 1"
            m = re.search(r'Race:?\s*(\d+)', txt, re.IGNORECASE)
            if m:
                current_race = int(m.group(1))
            continue
            
        # Check for Change Row
        if not current_race: continue
        
        cols = row.find_all('td')
        
        # Check for Race-wide cancellation row
        # Can be 1 column (colspan) or 2 columns (change + time)
        if len(cols) <= 2:
            # Check all cells for 'cancel'
            is_cancel = False
            txt = ""
            for c in cols:
                c_txt = c.get_text(strip=True)
                if 'cancel' in c_txt.lower():
                    is_cancel = True
                    txt = c_txt
                    break
            
            if is_cancel:
                changes.append({
                    'race_number': current_race,
                    'program_number': None,
                    'horse_name': "",
                    'change_type': 'Race Cancelled',
                    'description': txt
                })
                continue

        if len(cols) < 3: continue
        
        # Col 0: Horse (#1 Name)
        # Col 1: Name (sometimes separate?)
        # Let's inspect browser tool result:
        # Row: <td class="horse">#1</td> <td class="horse">Dirty Diana</td> <td class="changes">Scratched - Vet</td>
        
        horse_num_cell = row.find('td', class_='horse')
        if not horse_num_cell: 
            # Check if it's a "Race wide" change but with enough columns?
            change_cell = row.find('td', class_='changes')
            if change_cell:
                txt = change_cell.get_text(strip=True)
                if 'cancel' in txt.lower():
                     changes.append({
                        'race_number': current_race,
                        'program_number': None,
                        'horse_name': "",
                        'change_type': 'Race Cancelled',
                        'description': txt
                    })
            continue
        
        # Sometimes there are two cells with class 'horse' (number, then name)
        horse_cells = row.find_all('td', class_='horse')
        
        pgm = None
        horse_name = None
        change_desc = None
        
        if len(horse_cells) >= 2:
            pgm = horse_cells[0].get_text(strip=True).replace('#', '')
            horse_name = horse_cells[1].get_text(strip=True)
        elif len(horse_cells) == 1:
            # Maybe joined? "#1 Dirty Diana"
            full = horse_cells[0].get_text(strip=True)
            if '#' in full:
                parts = full.split(' ', 1)
                pgm = parts[0].replace('#', '')
                if len(parts) > 1: horse_name = parts[1]
            else:
                horse_name = full
                
        # Change description
        change_cell = row.find('td', class_='changes')
        if change_cell:
            change_desc = change_cell.get_text(strip=True)
            
        if change_desc:
            change_type = determine_change_type(change_desc)
            
            changes.append({
                'race_number': current_race,
                'program_number': normalize_pgm(pgm) if pgm else None,
                'horse_name': normalize_name(horse_name if horse_name else ""),
                'change_type': change_type,
                'description': change_desc
            })

    # Also check for whole race cancellation messages in the table or headers if possible
    # Some pages might have a row like "Race 5 Cancelled"
    # We rely on determine_change_type mostly, but let's check header too
    all_headers = target_table.find_all('th', class_='race')
    for h in all_headers:
        txt = h.get_text(strip=True)
        if 'cancel' in txt.lower():
            # Extract race number
            m = re.search(r'Race:?\s*(\d+)', txt, re.IGNORECASE)
            if m:
                r_num = int(m.group(1))
                changes.append({
                    'race_number': r_num,
                    'program_number': None,
                    'horse_name': "",
                    'change_type': 'Race Cancelled',
                    'description': txt
                })
            
    return changes

def update_changes_in_db(track_code, race_date, change_list):
    """
    Update database for found changes (scratches and others)
    """
    supabase = get_supabase_client()
    count = 0
    scratches_marked = 0
    
    # Pre-fetch existing changes for this track/date to avoid spamming queries
    # Actually, simpler to do it per item since we need specific race_id
    
    for item in change_list:
        try:
            # 1. Find Race ID
            race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{item['race_number']}"
            
            # Get Race
            r_res = supabase.table('hranalyzer_races').select('id').eq('race_key', race_key).execute()
            if not r_res.data:
                continue
                
            race_id = r_res.data[0]['id']
            
            # 2. Find Entry to mark
            entry_id = None
            
            # Try PGM match
            if item['program_number']:
                e_res = supabase.table('hranalyzer_race_entries')\
                    .select('id, scratched')\
                    .eq('race_id', race_id)\
                    .eq('program_number', item['program_number'])\
                    .execute()
                    
                if e_res.data:
                    entry = e_res.data[0]
                    entry_id = entry['id']
            
            # Fallback Name match
            if not entry_id and item['horse_name']:
                 all_entries = supabase.table('hranalyzer_race_entries')\
                    .select('id, hranalyzer_horses!inner(horse_name)')\
                    .eq('race_id', race_id)\
                    .execute()
                 
                 target_norm = item['horse_name']
                 for e in all_entries.data:
                     h_name = e['hranalyzer_horses']['horse_name']
                     if normalize_name(h_name) == target_norm:
                         entry_id = e['id']
                         break
            
            # ORPHAN PREVENTION:
            # If this is a horse-specific change but we found no horse, DO NOT insert as "Race-wide"
            horse_specific_types = ['Scratch', 'Jockey Change', 'Weight Change', 'Equipment Change']
            if item['change_type'] in horse_specific_types and not entry_id:
                logger.warning(f"⚠️ Skipping orphan {item['change_type']} for {track_code} R{item['race_number']} ({item['horse_name']}/{item['program_number']})")
                continue

            # 3. DEDUPLICATION / MERGE Logic
            # Check if this change already exists (same race, entry, and type)
            query = supabase.table('hranalyzer_changes')\
                .select('id, description')\
                .eq('race_id', race_id)\
                .eq('change_type', item['change_type'])
            
            if entry_id:
                query = query.eq('entry_id', entry_id)
            else:
                query = query.is_('entry_id', 'null')
            
            existing_res = query.execute()
            
            if existing_res.data:
                # Potential duplicate or update
                existing_record = existing_res.data[0]
                existing_desc = existing_record['description'] or ""
                new_desc = item['description']
                
                # If the new description is already contained or redundant, skip
                if new_desc in existing_desc:
                    continue
                
                # If they are different, merge them
                merged_desc = f"{existing_desc}; {new_desc}"
                # Limit size just in case
                if len(merged_desc) > 500: merged_desc = merged_desc[:497] + "..."
                
                supabase.table('hranalyzer_changes')\
                    .update({'description': merged_desc})\
                    .eq('id', existing_record['id'])\
                    .execute()
                count += 1
            else:
                # 4. INSERT into hranalyzer_changes
                change_record = {
                    'race_id': race_id,
                    'entry_id': entry_id,
                    'change_type': item['change_type'],
                    'description': item['description']
                }
                
                supabase.table('hranalyzer_changes').insert(change_record).execute()
                count += 1

            # 5. Side effects (Scratched flag, Race Status)
            if item['change_type'] == 'Scratch' and entry_id:
                supabase.table('hranalyzer_race_entries')\
                    .update({'scratched': True})\
                    .eq('id', entry_id)\
                    .execute()
                
                logger.info(f"✂️ MARKED SCRATCH: {track_code} R{item['race_number']} #{item['program_number']} ({item['description']})")
                scratches_marked += 1
            elif item['change_type'] == 'Race Cancelled':
                supabase.table('hranalyzer_races')\
                    .update({'race_status': 'cancelled'})\
                    .eq('id', race_id)\
                    .execute()
                logger.info(f"🚫 RACE CANCELLED: {track_code} R{item['race_number']} ({item['description']})")
            
        except Exception as e:
            logger.error(f"Error processing change {item}: {e}")
            
    return count

def crawl_otb_changes():
    """
    Fallback crawler for OffTrackBetting.com
    Returns number of changes processed.
    """
    logger.info("Starting Fallback Crawl: OTB Scratches & Changes")
    url = "https://www.offtrackbetting.com/scratches_changes.html"
    
    html = fetch_static_page(url)
    if not html:
        logger.error("Failed to fetch OTB page")
        return 0
        
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    # Locate the main table - usually has "Race Date:"
    main_table = None
    for t in tables:
        if 'Race Date:' in t.get_text():
            main_table = t
            break
            
    if not main_table:
        logger.warning("Could not find main table in OTB page")
        return 0
        
    rows = main_table.find_all('tr')
    
    current_track = None
    current_race = None
    changes_found = []
    
    last_pgm = None
    last_horse = None
    
    for row in rows:
        text = row.get_text(strip=True)
        
        # Track Header: "AQU : Aqueduct : Race: 1"
        if 'Change' in text and ':' in text:
             # Reset context on new track/race
             last_pgm = None
             last_horse = None
             # Try to parse "CODE : Name : Race: N"
             cols = row.find_all('td')
             if cols:
                 header_txt = cols[0].get_text(strip=True)
                 parts = header_txt.split(':')
                 if len(parts) >= 3:
                     current_track = parts[0].strip() # AQU
                     # Race number is usually last part " Race: 1" -> "1"
                     race_part = parts[-1].lower().replace('race', '').strip()
                     current_race = int(race_part) if race_part.isdigit() else None
             continue
             
        if not current_track or not current_race:
            continue
            
        # Change Row
        # #5  A Lister  Scratched - Reason Unavailable  10:04 am ET
        cols = row.find_all('td')
        if len(cols) < 3: continue
        
        pgm = None
        horse_name = None
        desc_cell = None
        
        # CASE 1: Full Row with Horse Info
        if len(cols) == 4 and '#' in cols[0].get_text():
            pgm = cols[0].get_text(strip=True).replace('#', '')
            horse_name_cell = cols[1].get_text(strip=True)
            if horse_name_cell:
                horse_name = horse_name_cell
            desc_cell = cols[2]
            
            # Update context
            last_pgm = pgm
            last_horse = horse_name
            
        # CASE 2: Continuation Row (just description)
        elif len(cols) == 3 and not '#' in cols[0].get_text():
             desc_cell = cols[1]
             # Reuse context
             pgm = last_pgm
             horse_name = last_horse
        
        # Parse description
        if desc_cell:
            raw_desc = desc_cell.get_text(" ", strip=True) # "Scratched - Reason"
            
            # IMPROVEMENT: Try to extract horse name from description if missing
            # Example: "A Lister Scratched - Reason"
            if not horse_name:
                # Naive check: does the description start with a known pattern?
                # Actually, blindly assigning last_horse is risky unless we are sure.
                # However, OTB usually puts the reason on the next line for the SAME horse.
                pass

            # Cleanup descriptions
            raw_desc = raw_desc.replace('\n', ' ').strip()
            
            # Determine type
            ctype = determine_change_type(raw_desc)
            
            # If we missed the horse name but the description implies a scratch...
            # We skip adding "Race-wide" Scratch if we suspect it belongs to a horse.
            # But how do we know?
            # Let's clean up "PrivVet-Injured" specifically.
            
            changes_found.append({
                'track_code': current_track,
                'race_number': current_race,
                'program_number': pgm, 
                'horse_name': horse_name,
                'change_type': ctype,
                'description': raw_desc
            })
    
    logger.info(f"OTB Crawl found {len(changes_found)} changes raw")
    
    # Group by track and update DB
    changes_by_track = {}
    for c in changes_found:
        t = c['track_code']
        if t not in changes_by_track: changes_by_track[t] = []
        changes_by_track[t].append({
            'race_number': c['race_number'],
            'program_number': c['program_number'],
            'horse_name': c['horse_name'],
            'change_type': c['change_type'],
            'description': c['description']
        })
        
    total_saved = 0
    today = date.today()
    for trk, chgs in changes_by_track.items():
        saved = update_changes_in_db(trk, today, chgs)
        total_saved += saved
        
    return total_saved


def crawl_late_changes():
    """
    Main entry point for crawling changes.
    Tries Equibase first, then OTB if needed.
    """
    logger.info("Starting Crawl: Equibase Late Changes")
    
    total_changes_processed = 0
    today = date.today()
    
    # 1. Try Equibase
    try:
        track_links = parse_late_changes_index()
        logger.info(f"Found {len(track_links)} tracks with changes on Equibase")
        
        for link in track_links:
            code = link['track_code']
            url = link['url']
            try:
                html = fetch_static_page(url)
                if html:
                    changes = parse_track_changes(html, code)
                    if changes:
                        count = update_changes_in_db(code, today, changes)
                        total_changes_processed += count
            except Exception as e:
                logger.error(f"Error crawling {code}: {e}")
                
    except Exception as e:
        logger.error(f"Equibase index fetch failed: {e}")
        
    logger.info(f"Equibase phase complete. Processed {total_changes_processed} records.")
    
    # 2. Run OTB Fallback/Supplement
    # Always run to catch exceptions and gaps
    logger.info("Starting OTB Fallback Crawl...")
    try:
        otb_count = crawl_otb_changes()
        total_changes_processed += otb_count
        logger.info(f"OTB Helper added {otb_count} records.")
    except Exception as e:
        logger.error(f"OTB Crawl failed: {e}")
        
    logger.info(f"Total Changes Processed (All Sources): {total_changes_processed}")
    return total_changes_processed

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    crawl_late_changes()
