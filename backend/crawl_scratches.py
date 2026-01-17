
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
        if len(cols) < 3: continue
        
        # Col 0: Horse (#1 Name)
        # Col 1: Name (sometimes separate?)
        # Let's inspect browser tool result:
        # Row: <td class="horse">#1</td> <td class="horse">Dirty Diana</td> <td class="changes">Scratched - Vet</td>
        
        horse_num_cell = row.find('td', class_='horse')
        if not horse_num_cell: continue
        
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
            
    return changes

def update_changes_in_db(track_code, race_date, change_list):
    """
    Update database for found changes (scratches and others)
    """
    supabase = get_supabase_client()
    count = 0
    scratches_marked = 0
    
    for item in change_list:
        try:
            # 1. Find Race ID
            race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{item['race_number']}"
            
            # Get Race
            r_res = supabase.table('hranalyzer_races').select('id').eq('race_key', race_key).execute()
            if not r_res.data:
                # Race might not exist if crawler hasn't run yet? 
                # Or maybe it's a new track we don't follow.
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
            
            # Fallback Name match (if PGM search failed or PGM matches nothing)
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
            
            # 3. UPSERT into hranalyzer_changes
            # Construct Change Record
            change_record = {
                'race_id': race_id,
                'entry_id': entry_id, # Can be None if horse not found (but we shouldn't insert if entry is missing? actually changes page might link to track info)
                                      # But for now, let's allow inserting even if entry_id is None (generic race change?) 
                                      # The SQL constraints might require unique entry_id per description? 
                                      # "CONSTRAINT unique_race_entry_change UNIQUE (race_id, entry_id, change_type, description)"
                                      # If entry_id is NULL, multiple NULLs are distinct in SQL usually. 
                                      # Let's ensure we skip if we can't find entry, unless it's a race-wide change.
                'change_type': item['change_type'],
                'description': item['description']
            }
            
            # Basic deduplication handled by SQL Unique Constraint (changes often repeat on the page)
            # Use upsert or ignore conflict
            try:
                res = supabase.table('hranalyzer_changes')\
                    .upsert(change_record, on_conflict='race_id,entry_id,change_type,description')\
                    .execute()
                
                # Check if it was actually inserted/updated (count > 0 in most libs, but supabase insert response might vary)
                count += 1
            except Exception as e:
                # likely duplicate or constraint violation if not using upsert correctly
                # logger.warning(f"Error inserting change: {e}")
                pass

            # 4. If Scratch, also update existing `scratches` boolean for backward compat
            if item['change_type'] == 'Scratch' and entry_id:
                # Only update if not already scratched to avoid redundancy?
                # Actually, idempotent update is fine.
                supabase.table('hranalyzer_race_entries')\
                    .update({'scratched': True})\
                    .eq('id', entry_id)\
                    .execute()
                
                start_sym = "✂️"
                logger.info(f"{start_sym} MARKED SCRATCH: {track_code} R{item['race_number']} #{item['program_number']} ({item['description']})")
                scratches_marked += 1
            elif item['change_type'] == 'Jockey Change':
                logger.info(f"🏇 JOCKEY CHANGE: {track_code} R{item['race_number']} #{item['program_number']} ({item['description']})")
                
        except Exception as e:
            logger.error(f"Error processing change {item}: {e}")
            
    return count

def crawl_late_changes():
    """
    Main entry point for crawling changes
    """
    logger.info("Starting Crawl: Equibase Late Changes")
    
    # 1. Get Track Links
    track_links = parse_late_changes_index()
    logger.info(f"Found {len(track_links)} tracks with changes")
    
    total_changes_processed = 0
    today = date.today()
    
    for link in track_links:
        code = link['track_code']
        url = link['url']
        
        try:
            # logger.info(f"Checking changes for {code}")
            html = fetch_static_page(url)
            if not html: continue
            
            changes = parse_track_changes(html, code)
            
            if changes:
                # logger.info(f"Found {len(changes)} changes for {code}")
                # Update DB
                processed = update_changes_in_db(code, today, changes)
                total_changes_processed += processed
                
        except Exception as e:
            logger.error(f"Error processing {code}: {e}")
            
    logger.info(f"Changes Crawl Complete. Processed {total_changes_processed} records.")
    return total_changes_processed

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    crawl_late_changes()
