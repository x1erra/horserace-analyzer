
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
            
            # Check for Incapsula/Bot blocking despite 200 OK
            is_blocked = "Pardon Our Interruption" in response.text or "Incapsula" in response.text
            
            if response.status_code == 200 and len(response.text) > 500 and not is_blocked:
                return response.text
            
            if is_blocked:
                logger.warning(f"Requests blocked (Incapsula). Status {response.status_code}. Falling back to PowerShell...")
            else:
                logger.warning(f"Requests got status {response.status_code}, trying PowerShell...")
            
        except requests.exceptions.Timeout:
            logger.warning(f"Requests timeout for {url}, trying PowerShell...")
        except Exception as e:
            logger.warning(f"Requests failed: {e}, trying PowerShell...")
        
        # Fallback to PowerShell
        try:
            temp_file = f"temp_scratches_{int(time.time())}_{attempt}.html"
            # Use basic parsing (BasicParsing) to avoid IE dependency issues if possible, but standard is fine
            cmd = ["powershell", "-Command", f"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_file}' -TimeoutSec 15 -UserAgent 'Mozilla/5.0'"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                try: os.remove(temp_file) 
                except: pass
                
                if len(content) > 500 and "Pardon Our Interruption" not in content:
                    return content
                else:
                    logger.warning("PowerShell also blocked or empty.")
                    
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
        if 'wagering' in desc_lower:
            return 'Wagering' # New type, or return 'Other' if we don't want to track it
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

def fetch_rss_feed(track_code):
    """
    Fetch RSS feed for a track.
    """
    url = f"https://www.equibase.com/static/latechanges/rss/{track_code}-USA.rss"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.text.startswith('<?xml'):
            return r.text
    except Exception as e:
        logger.warning(f"RSS fetch failed for {track_code}: {e}")
    return None

def parse_rss_changes(xml_content, track_code):
    """
    Parse RSS XML to extract changes.
    """
    soup = BeautifulSoup(xml_content, 'html.parser') # xml parser missing, fallback to html.parser
    items = soup.find_all('item')
    changes = []
    
    for item in items:
        desc = item.description.text if item.description else ""
        # Description contains multiple lines separated by <br/> (encoded or not)
        # BeautifulSoup XML parser might decode it.
        # Example: "Race 05: <b>...</b> <i>Race Cancelled</i> ..."
        
        # Split by <br/> tags
        lines = re.split(r'<br\s*/?>', desc)
        
        for line in lines:
            if not line.strip(): continue
            
            # 1. Race Cancelled
            # Race 05: <i>Race Cancelled</i> - Weather
            # or &lt;i&gt;Race Cancelled&lt;/i&gt; depending on parsing
            
            # Clean HTML tags from line for easier regex?
            # Or use regex that tolerates tags.
            # "Race (\d+):.*Race Cancelled.*- (.*)"
            
            m_cancel = re.search(r'Race\s*(\d+):.*?Race Cancelled.*?- (.*)', line, re.IGNORECASE | re.DOTALL)
            if m_cancel:
                changes.append({
                    'race_number': int(m_cancel.group(1)),
                    'program_number': None,
                    'horse_name': "",
                    'change_type': 'Race Cancelled',
                    'description': m_cancel.group(2).strip()
                })
                continue
                
            # 2. Scratch
            # Race 02: <b># 5 A Lister</b> <i>Scratched</i> - Reason Unavailable
            # Regex: Race (\d+):.*?#\s*(\S+)\s+(.*?)</b>.*?Scratched.*?-\s*(.*)
            # Be careful with <b> and </b> items.
            
            # Let's simple remove tags to parse structure
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            # "Race 02: # 5 A Lister Scratched - Reason Unavailable"
            # "Race 02: # 5 A Lister Scratch Reason - Reason Unavailable changed to PrivVet-Injured"
            
            # Parse Race Number
            m_race = re.match(r'Race\s*(\d+):', clean_line)
            if not m_race: continue
            r_num = int(m_race.group(1))
            
            content = clean_line[m_race.end():].strip()
            # "# 5 A Lister Scratched - Reason"
            
            # Parse Horse PGM + Name if present
            # "# 5 A Lister ..."
            pgm = None
            horse_name = None
            
            m_horse = re.match(r'#\s*(\w+)\s+(.*?)\s+(Scratched|Scratch Reason|Jockey|Weight|First Start|Gelding|Correction|Equipment|Workouts)', content, re.IGNORECASE)
            
            if m_horse:
                pgm = m_horse.group(1)
                horse_name = m_horse.group(2)
                keyword = m_horse.group(3) # "Scratched", "Jockey", etc.
                remainder = content[m_horse.end() - len(keyword):] # Start from keyword
            else:
                # Maybe no PGM?
                remainder = content
                
            # Determine Type
            ctype = 'Other'
            if 'scratched' in remainder.lower():
                ctype = 'Scratch'
            elif 'jockey' in remainder.lower():
                ctype = 'Jockey Change'
            elif 'weight' in remainder.lower():
                ctype = 'Weight Change'
            elif 'equipment' in remainder.lower():
                ctype = 'Equipment Change'
            elif 'cancel' in remainder.lower():
                if 'wagering' in remainder.lower():
                    ctype = 'Wagering'
                else:
                    ctype = 'Race Cancelled'
            
            desc = remainder
            
            changes.append({
                'race_number': r_num,
                'program_number': normalize_pgm(pgm) if pgm else None,
                'horse_name': normalize_name(horse_name if horse_name else ""),
                'change_type': ctype,
                'description': desc
            })
            
    return changes

def process_rss_for_track(track_code):
    """
    Crawl RSS for a specific track and return count of processed.
    """
    logger.info(f"Checking RSS for {track_code}...")
    xml = fetch_rss_feed(track_code)
    if not xml: return 0
    
    changes = parse_rss_changes(xml, track_code)
    logger.info(f"RSS found {len(changes)} changes/cancellations for {track_code}")
    
    today = date.today()
    return update_changes_in_db(track_code, today, changes)

CANCELLATIONS_URL = "https://www.equibase.com/static/latechanges/html/cancellations.html" # Keep for reference or if it starts working


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
                # SMART DEDUPLICATION
                existing_record = existing_res.data[0]
                existing_desc = existing_record['description'] or ""
                new_desc = item['description']
                
                should_update = False
                final_desc = existing_desc

                # A) Priority Overwrite: If existing is "Unavailable" and new is specific, take new
                if "Reason Unavailable" in existing_desc and "Reason Unavailable" not in new_desc:
                    final_desc = new_desc
                    should_update = True
                
                # B) Ignore: If existing is specific and new is "Unavailable", keep existing
                elif "Reason Unavailable" not in existing_desc and "Reason Unavailable" in new_desc:
                    should_update = False
                    # Do nothing
                    
                # C) Merge: If both are valid, merge if different
                else:
                    if new_desc not in existing_desc:
                         final_desc = f"{existing_desc}; {new_desc}"
                         if len(final_desc) > 500: final_desc = final_desc[:497] + "..."
                         should_update = True
                
                if should_update:
                    supabase.table('hranalyzer_changes')\
                        .update({'description': final_desc})\
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
                
                try:
                    supabase.table('hranalyzer_changes').insert(change_record).execute()
                    count += 1
                except Exception as e:
                    logger.warning(f"Insert race condition (or duplicate) for {track_code} R{item['race_number']}: {e}")

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
    # ... (Keep existing OTB logic as is for now, heavily truncated for brevity in replacement if needed, 
    # but since I'm replacing from line 273, I need to keep it or just reference it?)
    # Wait, I shouldn't truncate OTB logic if I'm replacing the whole file bottom or a large chunk.
    # The user asked to modify crawl_scratches.py.
    # I will assume I need to keep OTB logic intact.
    
    # RE-IMPLEMENTING OTB fetch to ensure file integrity since I am replacing a huge chunk
    logger.info("Starting Fallback Crawl: OTB Scratches & Changes")
    url = "https://www.offtrackbetting.com/scratches_changes.html"
    
    html = fetch_static_page(url)
    if not html:
        logger.error("Failed to fetch OTB page")
        return 0
        
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    main_table = None
    for t in tables:
        if 'Race Date:' in t.get_text():
            main_table = t
            break
            
    today = date.today() # Target date
    
    # 1. Validate Date
    if 'Race Date:' not in main_table.get_text():
        logger.warning("OTB: Could not find Race Date header.")
        return 0
        
    # Extract date text "Race Date: 01/18/2026"
    date_valid = False
    try:
        import re
        txt = main_table.get_text()
        m = re.search(r'Race Date:\s*(\d{1,2}/\d{1,2}/\d{4})', txt)
        if m:
            page_date_str = m.group(1)
            # Parse MM/DD/YYYY
            page_date = datetime.strptime(page_date_str, '%m/%d/%Y').date()
            if page_date == today:
                date_valid = True
            else:
                logger.warning(f"OTB: Stale date found. Page: {page_date}, Expected: {today}. SKIPPING OTB.")
                return 0
    except Exception as e:
        logger.warning(f"OTB: Date validation error: {e}")
        return 0
        
    if not date_valid:
        return 0

    rows = main_table.find_all('tr')
    
    current_track = None
    current_race = None
    changes_found = []
    
    last_pgm = None
    last_horse = None
    
    for row in rows:
        text = row.get_text(strip=True)
        if 'Change' in text and ':' in text:
             last_pgm = None
             last_horse = None
             cols = row.find_all('td')
             if cols:
                 header_txt = cols[0].get_text(strip=True)
                 parts = header_txt.split(':')
                 if len(parts) >= 3:
                     current_track = parts[0].strip()
                     race_part = parts[-1].lower().replace('race', '').strip()
                     current_race = int(race_part) if race_part.isdigit() else None
             continue
             
        if not current_track or not current_race: continue
            
        cols = row.find_all('td')
        if len(cols) < 3: continue
        
        pgm = None
        horse_name = None
        desc_cell = None
        
        if len(cols) == 4 and '#' in cols[0].get_text():
            pgm = cols[0].get_text(strip=True).replace('#', '')
            horse_name = cols[1].get_text(strip=True)
            desc_cell = cols[2]
            last_pgm = pgm
            last_horse = horse_name
            
        elif len(cols) == 3 and not '#' in cols[0].get_text():
             # Strict check: preventing spillover if this row lacks structure
             # Only assume spillover if last_horse is set AND this row looks like a continuation
             # But OTB format for "Reason" alone usually implies it belongs to above.
             desc_cell = cols[1]
             pgm = last_pgm
             horse_name = last_horse
        
        if desc_cell:
            raw_desc = desc_cell.get_text(" ", strip=True).replace('\n', ' ').strip()
            ctype = determine_change_type(raw_desc)
            changes_found.append({
                'track_code': current_track,
                'race_number': current_race,
                'program_number': pgm, 
                'horse_name': horse_name,
                'change_type': ctype,
                'description': raw_desc
            })
    
    changes_by_track = {}
    for c in changes_found:
        t = c['track_code']
        if t not in changes_by_track: changes_by_track[t] = []
        changes_by_track[t].append(c)
        
    total_saved = 0
    today = date.today()
    for trk, chgs in changes_by_track.items():
        total_saved += update_changes_in_db(trk, today, chgs)
        
    return total_saved


def crawl_late_changes(reset_first=False):
    """
    Main entry point for crawling changes.
    """
    logger.info(f"Starting Crawl: Equibase Late Changes (Reset={reset_first})")
    
    total_changes_processed = 0
    today = date.today()
    
    # Reset Logic
    if reset_first:
        # We need a list of active tracks to reset.
        # We'll use the same active track discovery logic.
        pass # Will be handled inside the discovery loop or separate query?
        # Actually better to do it per track as we find them valid?
        # No, reset implies "I want a clean slate". 
        # But we only know *active* tracks for today from DB races.
        # So we query active tracks first.

    
    # 0. CHECK RSS FEEDS (Primary method now due to Equibase blocking)
    logger.info("Checking RSS feeds for active tracks...")
    
    # Get active tracks from DB for today
    today_str = today.strftime('%Y%m%d')
    supabase = get_supabase_client()
    try:
        # Get unique track codes for races today
        res = supabase.table('hranalyzer_races')\
            .select('race_key')\
            .like('race_key', f"%-{today_str}-%")\
            .execute()
        
        active_tracks = set()
        if res.data:
            for r in res.data:
                # key: AQU-20260117-1
                parts = r['race_key'].split('-')
                if len(parts) >= 1:
                    active_tracks.add(parts[0])
        
        logger.info(f"Active tracks to scan: {list(active_tracks)}")
        
        # EXECUTE RESET if requested
        if reset_first:
            for trk in active_tracks:
                reset_scratches_for_date(trk, today)
        
        for trk in active_tracks:
            cnt = process_rss_for_track(trk)
            total_changes_processed += cnt
            
    except Exception as e:
        logger.error(f"RSS Scan Loop failed: {e}")

    # 1. Try Equibase Track Pages (HTML Fallback)
    try:
        track_links = parse_late_changes_index() # This might be blocked too
        if track_links:
            logger.info(f"Found {len(track_links)} tracks with changes on Equibase HTML index")
            for link in track_links:
                code = link['track_code']
                # Skip if we already did RSS for this track? 
                # Maybe good to double check but duplicates are handled.
                # If RSS fails, this might work (via PowerShell)
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
        
    logger.info(f"Equibase phase complete. Total records: {total_changes_processed}")
    
    # 2. Run OTB Fallback
    logger.info("Starting OTB Fallback Crawl...")
    try:
        otb_count = crawl_otb_changes()
        total_changes_processed += otb_count
        logger.info(f"OTB Helper added records.")
    except Exception as e:
        logger.error(f"OTB Crawl failed: {e}")
        
    return total_changes_processed

def reset_scratches_for_date(track_code, race_date):
    """
    Hard reset scratches for a track/date. 
    Used when we suspect 'ghost scratches' from bad crawl data.
    """
    logger.info(f"RESETTING SCRATCHES for {track_code} on {race_date}")
    supabase = get_supabase_client()
    
    try:
        race_date_str = race_date.strftime('%Y-%m-%d')
        
        # 1. Get relevant race IDs
        races = supabase.table('hranalyzer_races')\
            .select('id')\
            .eq('track_code', track_code)\
            .eq('race_date', race_date_str)\
            .execute()
            
        race_ids = [r['id'] for r in races.data]
        if not race_ids:
            logger.warning("No races found to reset.")
            return
            
        # 2. Un-scratch ALL entries in these races
        supabase.table('hranalyzer_race_entries')\
            .update({'scratched': False})\
            .in_('race_id', race_ids)\
            .execute()
            
        # 3. Delete ALL detailed changes from hranalyzer_changes for these races
        # This ensures we remove stale "Jockey Changes", "Owner Changes", etc. that are no longer valid.
        supabase.table('hranalyzer_changes')\
            .delete()\
            .in_('race_id', race_ids)\
            .execute()
            
        logger.info(f"Successfully reset scratches for {len(race_ids)} races.")
        
    except Exception as e:
        logger.error(f"Failed to reset scratches: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    crawl_late_changes()
