"""
DRF PDF Parser
Parses Daily Racing Form PDFs to extract pre-race data for upcoming races
"""

import pdfplumber
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from supabase_client import get_supabase_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# NORMALIZATION FUNCTIONS
# ==========================================

def normalize_horse_name(name: str) -> str:
    """Normalize horse name (remove extra spaces, standardize case)"""
    if not name:
        return ""
    return ' '.join(name.strip().upper().split())


def normalize_person_name(name: str) -> str:
    """Normalize jockey/trainer/owner name"""
    if not name:
        return ""
    # Remove extra spaces and standardize
    name = ' '.join(name.strip().split())
    # Capitalize each word
    return name.title()


def parse_odds(odds_str: str) -> Optional[str]:
    """
    Parse and standardize odds format
    Examples: "3-1", "5/2", "7-5" -> standardize to "X-Y" format
    """
    if not odds_str:
        return None

    odds_str = odds_str.strip()

    # Already in X-Y format
    if re.match(r'\d+-\d+', odds_str):
        return odds_str

    # Convert X/Y to X-Y
    if '/' in odds_str:
        return odds_str.replace('/', '-')

    # Single number (even money, etc.)
    if odds_str.isdigit():
        return f"{odds_str}-1"

    return odds_str


def parse_distance(distance_str: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse distance and convert to feet
    Examples: "6F", "6 Furlongs", "1 Mile" -> ("6 Furlongs", 3960)
    """
    if not distance_str:
        return None, None

    distance_str = distance_str.strip().upper()

    # Furlongs
    if 'F' in distance_str or 'FURLONG' in distance_str:
        match = re.search(r'(\d+)', distance_str)
        if match:
            furlongs = int(match.group(1))
            feet = furlongs * 660  # 1 furlong = 660 feet
            return f"{furlongs} Furlongs", feet

    # Miles
    if 'M' in distance_str or 'MILE' in distance_str:
        # Handle fractional miles like "1 1/8"
        if '/' in distance_str:
            parts = re.findall(r'(\d+)', distance_str)
            if len(parts) >= 3:
                whole = int(parts[0])
                numerator = int(parts[1])
                denominator = int(parts[2])
                miles = whole + (numerator / denominator)
                feet = int(miles * 5280)
                return f"{whole} {numerator}/{denominator} Miles", feet
        else:
            match = re.search(r'(\d+)', distance_str)
            if match:
                miles = int(match.group(1))
                feet = miles * 5280
                return f"{miles} Mile{'s' if miles > 1 else ''}", feet

    # Yards
    if 'Y' in distance_str or 'YARD' in distance_str:
        match = re.search(r'(\d+)', distance_str)
        if match:
            yards = int(match.group(1))
            feet = yards * 3
            return f"{yards} Yards", feet

    return distance_str, None


# ==========================================
# METADATA EXTRACTION
# ==========================================

def extract_header_metadata(first_page) -> Dict:
    """
    Extract track name and date from first page header
    Returns: {'track_code': 'GP', 'track_name': 'Gulfstream Park', 'race_date': '2026-01-01'}
    """
    text = first_page.extract_text()

    # Track mapping (expand as needed)
    track_mapping = {
        'GULFSTREAMPARK': 'GP',
        'GULFSTREAM': 'GP',
        'AQUEDUCT': 'AQU',
        'BELMONT': 'BEL',
        'CHURCHILL': 'CD',
        'SANTA ANITA': 'SA',
        'SANTAANITA': 'SA',
        'SARATOGA': 'SAR',
        'KEENELAND': 'KEE',
        'DELMAR': 'DMR',
        'DEL MAR': 'DMR',
        'FAIRGROUNDS': 'FG',
        'FAIR GROUNDS': 'FG',
        'SAMHOUSTON': 'HOU',
        'SAM HOUSTON': 'HOU',
        'TAMPABADOWNS': 'TAM',
        'TAMPA BAY': 'TAM',
    }

    metadata = {
        'track_code': None,
        'track_name': None,
        'race_date': None
    }

    # Extract track name (handle formats like "GulfstreamPark")
    text_upper = text.upper().replace(' ', '')  # Remove spaces to match concatenated names
    for track_name, code in track_mapping.items():
        if track_name.replace(' ', '') in text_upper:
            metadata['track_code'] = code
            # Format track name nicely
            if code == 'GP':
                metadata['track_name'] = 'Gulfstream Park'
            elif code == 'SA':
                metadata['track_name'] = 'Santa Anita'
            elif code == 'DMR':
                metadata['track_name'] = 'Del Mar'
            elif code == 'FG':
                metadata['track_name'] = 'Fair Grounds'
            elif code == 'HOU':
                metadata['track_name'] = 'Sam Houston'
            else:
                metadata['track_name'] = track_name.replace('PARK', ' Park').replace('DOWNS', ' Downs').title()
            break

    # Extract date - try multiple formats
    # Format 1: (M/D/YYYY) or (MM/DD/YYYY)
    date_pattern1 = r'\((\d{1,2}/\d{1,2}/\d{4})\)'
    date_match1 = re.search(date_pattern1, text)
    if date_match1:
        date_str = date_match1.group(1)
        try:
            parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
            metadata['race_date'] = parsed_date.strftime("%Y-%m-%d")
        except:
            logger.warning(f"Could not parse date format 1: {date_str}")

    # Format 2: "WEDNESDAY, JANUARY 1, 2026"
    if not metadata['race_date']:
        date_pattern2 = r'([A-Z]+,\s+[A-Z]+\s+\d{1,2},\s+\d{4})'
        date_match2 = re.search(date_pattern2, text.upper())
        if date_match2:
            date_str = date_match2.group(1)
            try:
                parsed_date = datetime.strptime(date_str, "%A, %B %d, %Y")
                metadata['race_date'] = parsed_date.strftime("%Y-%m-%d")
            except:
                logger.warning(f"Could not parse date format 2: {date_str}")

    return metadata


# ==========================================
# RACE PARSING
# ==========================================

def is_race_header_page(page_text: str) -> Tuple[bool, Optional[int]]:
    """
    Determine if this page is a race header page
    Returns: (is_header, race_number)

    Race header pages have this format:
    Line 1: Daily Racing Form GulfstreamPark(1/1/2026)
    Line 2: Race number (just a digit)
    Line 3: Track name
    Line 4: Race class
    """
    lines = page_text.split('\n')

    if len(lines) < 4:
        return False, None

    # Check line 2 for standalone race number
    line2 = lines[1].strip()
    if not line2.isdigit():
        return False, None

    race_number = int(line2)

    # Check line 3 for track name (not horse info)
    line3 = lines[2].strip()

    # Race header pages have track name on line 3
    # Horse entry pages have horse names/breeding info
    # Track names contain "Park", "Downs", or are standalone track names
    if any(track in line3.upper() for track in ['GULFSTREAM PARK', 'GULFSTREAM', 'PARK', 'DOWNS']):
        # Make sure it's not a horse entry (which would have "Life", "Sire:", etc.)
        if 'LIFE' not in page_text[:500].upper() or line3.strip() == 'Gulfstream Park':
            return True, race_number

    return False, None


def extract_race_header_from_page(page_text: str, race_number: int) -> Dict:
    """
    Extract race metadata AND horses from a race header page
    Format:
    Line 2: Race number
    Line 3: Track name
    Line 4: Race class
    Line 5: Distance/surface, race type, purse
    Line 6+: Conditions
    Post time line: "Posttime:1:20ET"
    Then: Horses with condensed PP data (program number, name, past races)

    Returns race data dict with embedded entries
    """
    lines = page_text.split('\n')

    race_data = {
        'race_number': race_number,
        'post_time': None,
        'race_type': None,
        'surface': 'Dirt',  # Default
        'distance': None,
        'distance_feet': None,
        'purse': None,
        'conditions': None,
        'embedded_entries': []  # Horses listed on this header page
    }

    # Join all text for easier pattern matching
    full_text = page_text

    # Extract distance and surface
    # Examples: "5ôFurlongs (Tapeta)", "1 MILE (Turf)", "1MILE"
    distance_pattern = r'(\d+[\sô]*(?:FURLONG|MILE|YARD)[S]?)'
    distance_match = re.search(distance_pattern, full_text.upper())
    if distance_match:
        distance_str, distance_feet = parse_distance(distance_match.group(1))
        race_data['distance'] = distance_str
        race_data['distance_feet'] = distance_feet

    # Extract surface
    if 'TURF' in full_text.upper():
        race_data['surface'] = 'Turf'
    elif 'TAPETA' in full_text.upper() or 'SYNTHETIC' in full_text.upper():
        race_data['surface'] = 'Synthetic'
    else:
        race_data['surface'] = 'Dirt'

    # Extract race type
    race_types = ['CLAIMING', 'ALLOWANCE', 'STAKES', 'MAIDEN', 'HANDICAP']
    for race_type in race_types:
        if race_type in full_text.upper():
            race_data['race_type'] = race_type.title()
            break

    # Extract purse - first occurrence of $XX,XXX pattern
    purse_match = re.search(r'Purse\$?([\d,]+)', full_text)
    if purse_match:
        race_data['purse'] = f"${purse_match.group(1)}"

    # Extract post time - format: "Posttime:12:50ET" or "Posttime:1:20ET"
    time_pattern = r'Posttime:(\d{1,2}:\d{2})\s*ET'
    time_match = re.search(time_pattern, full_text)
    if time_match:
        race_data['post_time'] = time_match.group(1)

    # Extract conditions - lines between purse and post time typically
    # Look for descriptive text starting with "For" or "Weight"
    conditions_lines = []
    for i, line in enumerate(lines[4:10]):  # Check lines 5-10
        line = line.strip()
        if line and (line.startswith('For') or line.startswith('Weight') or
                     line.startswith('Fillies') or line.startswith('ClaimingPrice') or
                     'Year' in line or 'Upward' in line):
            conditions_lines.append(line)

    if conditions_lines:
        race_data['conditions'] = ' '.join(conditions_lines)

    # Extract horses embedded in this page
    # After the post time line, horses are listed with program numbers
    # Format: standalone digit on a line, then horse name and PP data
    post_time_found = False
    current_prog_num = None

    for i, line in enumerate(lines):
        # Once we find post time, start looking for horses
        if 'Posttime:' in line:
            post_time_found = True
            continue

        if post_time_found:
            # Check if this line is just a digit (program number)
            line_stripped = line.strip()

            if line_stripped.isdigit() and len(line_stripped) <= 2:
                # This is a program number
                current_prog_num = line_stripped

            # Check if next line has horse name (contains breeding info, "Life", etc.)
            elif current_prog_num and i + 1 < len(lines):
                next_line = lines[i + 1] if i + 1 < len(lines) else ""

                # Horse name line typically has: "HorseName Color.g.Age(...) Life XX ..."
                if 'Life' in next_line or 'Sire:' in next_line or '.m.' in next_line or '.g.' in next_line or '.f.' in next_line:
                    # Extract horse name (first word before space and color/age info)
                    horse_match = re.match(r'^([A-Za-z\']+)', line)
                    if horse_match:
                        horse_name = horse_match.group(1).strip()
                        race_data['embedded_entries'].append({
                            'program_number': current_prog_num,
                            'horse_name': normalize_horse_name(horse_name)
                        })
                    current_prog_num = None

    return race_data


# ==========================================
# ENTRY PARSING
# ==========================================

def is_horse_entry_page(page_text: str) -> bool:
    """
    Determine if this page is a horse continuation page with one or more horses
    Returns: True if this is a continuation page with horses

    Continuation pages have:
    Line 1: Daily Racing Form GulfstreamPark(1/1/2026)
    Line 2: Program number (digit)
    Line 3: Horse name with breeding info (contains "Life", "Sire:", etc.)
    """
    lines = page_text.split('\n')

    if len(lines) < 3:
        return False

    # Check line 2 for program number
    line2 = lines[1].strip()
    if not line2.isdigit():
        return False

    # Check if it's a horse entry (has "Life", "Sire:", breeding info)
    if 'LIFE' in page_text[:500].upper() or 'SIRE:' in page_text[:500].upper():
        line3 = lines[2] if len(lines) > 2 else ""
        # Check if line 3 has horse name pattern (starts with letters and has Life or breed info)
        if re.match(r'^[A-Za-z\']+', line3) and ('Life' in line3 or '.m.' in line3 or '.g.' in line3 or '.f.' in line3 or '.c.' in line3):
            return True

    return False


def extract_all_horses_from_page(page_text: str) -> List[Dict]:
    """
    Extract ALL horses from a continuation page
    Returns: List of entry dicts

    Continuation pages can have multiple horses, each with format:
    - Program number on its own line (single digit)
    - Horse name and breeding info on next line (contains "Life")
    """
    lines = page_text.split('\n')
    horses = []

    i = 0
    while i < len(lines):
        line_stripped = lines[i].strip()

        # Check if this line is a program number (single digit, 1-12)
        if line_stripped.isdigit() and len(line_stripped) <= 2:
            prog_num = int(line_stripped)
            if prog_num >= 1 and prog_num <= 20:  # Valid program numbers
                # Check next line for horse name
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # Horse line should have: Name + breed info + "Life"
                    if 'Life' in next_line or '.m.' in next_line or '.g.' in next_line or '.f.' in next_line or '.c.' in next_line:
                        horse_name_match = re.match(r'^([A-Za-z\']+)', next_line)
                        if horse_name_match:
                            horse_name = horse_name_match.group(1).strip()

                            # Create entry (basic info for now)
                            entry = {
                                'program_number': str(prog_num),
                                'horse_name': normalize_horse_name(horse_name),
                                'jockey': None,
                                'trainer': None,
                                'owner': None,
                                'morning_line_odds': None,
                                'weight': None,
                                'medication': None,
                                'equipment': None
                            }
                            horses.append(entry)

        i += 1

    return horses


def extract_entry_from_page(page_text: str, program_number: int, horse_name: str) -> Dict:
    """
    Extract horse entry details from an entry page

    For now, extract basic info. Past performance parsing can be added later.
    """
    lines = page_text.split('\n')

    entry = {
        'program_number': str(program_number),
        'horse_name': normalize_horse_name(horse_name) if horse_name else None,
        'jockey': None,
        'trainer': None,
        'owner': None,
        'morning_line_odds': None,
        'weight': None,
        'medication': None,
        'equipment': None
    }

    # Look for Blinkers ON/OFF
    if 'BLINKERSON' in page_text.replace(' ', '').upper():
        entry['equipment'] = 'Blinkers'

    # Look for medication (Lasix is common)
    if re.search(r'\bL\d{3}\b', page_text):  # L120, L122, etc. indicates Lasix + weight
        entry['medication'] = 'Lasix'
        # Extract weight
        weight_match = re.search(r'L(\d{3})', page_text)
        if weight_match:
            entry['weight'] = int(weight_match.group(1))

    # Look for trainer info - usually has "Tr:" or "Trainer:"
    trainer_pattern = r'Tr:\s*([A-Z][A-Za-z\s\.]+?)(?:\(|2025:|Life)'
    trainer_match = re.search(trainer_pattern, page_text)
    if trainer_match:
        entry['trainer'] = trainer_match.group(1).strip()

    # Jockey is harder to extract from PP pages - would need more complex parsing
    # Owner info is also embedded in complex format

    return entry


# ==========================================
# DATABASE INSERTION
# ==========================================

def get_or_create_track(supabase, track_code: str, track_name: str) -> Optional[str]:
    """Get track ID or create if doesn't exist"""
    try:
        # Try to find existing track
        response = supabase.table('hranalyzer_tracks').select('id').eq('track_code', track_code).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]['id']

        # Create new track
        new_track = supabase.table('hranalyzer_tracks').insert({
            'track_code': track_code,
            'track_name': track_name or track_code
        }).execute()

        return new_track.data[0]['id'] if new_track.data else None
    except Exception as e:
        logger.error(f"Error getting/creating track {track_code}: {e}")
        return None


def get_or_create_horse(supabase, horse_name: str) -> Optional[str]:
    """Get horse ID or create if doesn't exist"""
    try:
        normalized_name = normalize_horse_name(horse_name)
        if not normalized_name:
            return None

        # Try to find existing horse
        response = supabase.table('hranalyzer_horses').select('id').eq('horse_name', normalized_name).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]['id']

        # Create new horse
        new_horse = supabase.table('hranalyzer_horses').insert({
            'horse_name': normalized_name
        }).execute()

        return new_horse.data[0]['id'] if new_horse.data else None
    except Exception as e:
        logger.error(f"Error getting/creating horse {horse_name}: {e}")
        return None


def get_or_create_jockey(supabase, jockey_name: str) -> Optional[str]:
    """Get jockey ID or create if doesn't exist"""
    if not jockey_name:
        return None

    try:
        normalized_name = normalize_person_name(jockey_name)

        response = supabase.table('hranalyzer_jockeys').select('id').eq('jockey_name', normalized_name).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]['id']

        new_jockey = supabase.table('hranalyzer_jockeys').insert({
            'jockey_name': normalized_name
        }).execute()

        return new_jockey.data[0]['id'] if new_jockey.data else None
    except Exception as e:
        logger.error(f"Error getting/creating jockey {jockey_name}: {e}")
        return None


def get_or_create_trainer(supabase, trainer_name: str) -> Optional[str]:
    """Get trainer ID or create if doesn't exist"""
    if not trainer_name:
        return None

    try:
        normalized_name = normalize_person_name(trainer_name)

        response = supabase.table('hranalyzer_trainers').select('id').eq('trainer_name', normalized_name).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]['id']

        new_trainer = supabase.table('hranalyzer_trainers').insert({
            'trainer_name': normalized_name
        }).execute()

        return new_trainer.data[0]['id'] if new_trainer.data else None
    except Exception as e:
        logger.error(f"Error getting/creating trainer {trainer_name}: {e}")
        return None


def insert_race_to_db(supabase, race_data: Dict, track_id: str, track_code: str, race_date: str, pdf_path: str) -> Optional[str]:
    """Insert race into database and return race ID"""
    try:
        # Build race key
        race_key = f"{track_code}-{race_date.replace('-', '')}-{race_data['race_number']}"

        # Check if race already exists
        existing = supabase.table('hranalyzer_races').select('id').eq('race_key', race_key).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"Race {race_key} already exists, skipping")
            return existing.data[0]['id']

        # Determine race status based on date
        # If race date is in the past, mark as 'past_drf_only' (has DRF data but no results yet)
        # If race date is today or future, mark as 'upcoming'
        from datetime import date as date_class
        race_date_obj = datetime.strptime(race_date, '%Y-%m-%d').date()
        today = date_class.today()

        if race_date_obj < today:
            # Past race from DRF - awaiting results from crawler
            race_status = 'past_drf_only'
        else:
            # Today or future race
            race_status = 'upcoming'

        # Insert race
        race_insert = {
            'race_key': race_key,
            'track_id': track_id,
            'track_code': track_code,
            'race_date': race_date,
            'race_number': race_data['race_number'],
            'post_time': race_data.get('post_time'),
            'race_type': race_data.get('race_type'),
            'surface': race_data.get('surface'),
            'distance': race_data.get('distance'),
            'distance_feet': race_data.get('distance_feet'),
            'purse': race_data.get('purse'),
            'conditions': race_data.get('conditions'),
            'race_status': race_status,
            'data_source': 'drf',
            'drf_pdf_path': pdf_path
        }

        new_race = supabase.table('hranalyzer_races').insert(race_insert).execute()

        if new_race.data and len(new_race.data) > 0:
            return new_race.data[0]['id']

        return None
    except Exception as e:
        logger.error(f"Error inserting race: {e}")
        return None


def insert_entries_to_db(supabase, race_id: str, entries: List[Dict]) -> int:
    """Insert race entries into database, return count"""
    inserted_count = 0

    for entry in entries:
        try:
            # Get or create related entities
            horse_id = get_or_create_horse(supabase, entry['horse_name']) if entry['horse_name'] else None
            jockey_id = get_or_create_jockey(supabase, entry['jockey']) if entry['jockey'] else None
            trainer_id = get_or_create_trainer(supabase, entry['trainer']) if entry['trainer'] else None

            if not horse_id:
                logger.warning(f"Skipping entry {entry['program_number']} - no horse name")
                continue

            # Insert entry
            entry_insert = {
                'race_id': race_id,
                'horse_id': horse_id,
                'jockey_id': jockey_id,
                'trainer_id': trainer_id,
                'program_number': entry['program_number'],
                'morning_line_odds': entry.get('morning_line_odds'),
                'weight': entry.get('weight'),
                'medication': entry.get('medication'),
                'equipment': entry.get('equipment')
            }

            supabase.table('hranalyzer_race_entries').insert(entry_insert).execute()
            inserted_count += 1

        except Exception as e:
            logger.error(f"Error inserting entry {entry.get('program_number')}: {e}")
            continue

    return inserted_count


# ==========================================
# MAIN PARSING FUNCTION
# ==========================================

def parse_drf_pdf(pdf_path: str, upload_log_id: Optional[str] = None) -> Dict:
    """
    Main entry point for parsing DRF PDF (page-by-page approach)
    Returns: {
        'success': True/False,
        'races_count': int,
        'entries_count': int,
        'error': str (if failed)
    }
    """
    try:
        supabase = get_supabase_client()

        with pdfplumber.open(pdf_path) as pdf:
            # Extract metadata from first page
            metadata = extract_header_metadata(pdf.pages[0])

            if not metadata['track_code'] or not metadata['race_date']:
                return {
                    'success': False,
                    'error': 'Could not extract track code or date from PDF'
                }

            logger.info(f"Parsing {metadata['track_name']} ({metadata['track_code']}) - {metadata['race_date']}")

            # Get or create track
            track_id = get_or_create_track(supabase, metadata['track_code'], metadata['track_name'])
            if not track_id:
                return {
                    'success': False,
                    'error': 'Could not get/create track in database'
                }

            # Parse races page by page
            races_data = []
            current_race = None
            current_race_entries = []
            race_1_entries = []  # Special handling for Race 1 (no header page)

            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if not page_text:
                    continue

                # Skip index page (page 1)
                if page_num == 0 and 'INDEXTOENTRIES' in page_text.replace(' ', ''):
                    continue

                # Check if this is a race header page
                is_header, race_number = is_race_header_page(page_text)

                if is_header:
                    # If this is Race 2 header and we have Race 1 entries, save Race 1 first
                    if race_number == 2 and len(race_1_entries) > 0:
                        race_1 = {
                            'race_number': 1,
                            'post_time': None,
                            'race_type': None,
                            'surface': 'Dirt',  # Default
                            'distance': None,
                            'distance_feet': None,
                            'purse': None,
                            'conditions': None,
                            'entries': race_1_entries
                        }
                        races_data.append(race_1)
                        logger.info(f"Found race 1 with {len(race_1_entries)} entries")

                    # Save previous race if exists
                    if current_race:
                        # Combine embedded entries from header + separate PP page entries
                        # Use dict to deduplicate by program number (prefer separate PP page data)
                        all_entries = {}

                        # First add embedded entries from header
                        for entry in current_race.get('embedded_entries', []):
                            all_entries[entry['program_number']] = {
                                'program_number': entry['program_number'],
                                'horse_name': entry['horse_name'],
                                'jockey': None,
                                'trainer': None,
                                'owner': None,
                                'morning_line_odds': None,
                                'weight': None,
                                'medication': None,
                                'equipment': None
                            }

                        # Then add/override with separate PP page entries (more detailed)
                        for entry in current_race_entries:
                            all_entries[entry['program_number']] = entry

                        current_race['entries'] = list(all_entries.values())
                        races_data.append(current_race)
                        logger.info(f"Found race {current_race['race_number']} with {len(current_race['entries'])} entries")

                    # Start new race
                    current_race = extract_race_header_from_page(page_text, race_number)
                    current_race_entries = []

                else:
                    # Check if this is a horse continuation page
                    is_entry_page = is_horse_entry_page(page_text)

                    if is_entry_page:
                        # Extract ALL horses from this page
                        entries = extract_all_horses_from_page(page_text)

                        if current_race:
                            # Add all entries to current race
                            current_race_entries.extend(entries)
                        else:
                            # Before any race header - must be Race 1
                            race_1_entries.extend(entries)

            # Don't forget the last race
            if current_race:
                # Combine embedded entries from header + separate PP page entries
                all_entries = {}

                # First add embedded entries from header
                for entry in current_race.get('embedded_entries', []):
                    all_entries[entry['program_number']] = {
                        'program_number': entry['program_number'],
                        'horse_name': entry['horse_name'],
                        'jockey': None,
                        'trainer': None,
                        'owner': None,
                        'morning_line_odds': None,
                        'weight': None,
                        'medication': None,
                        'equipment': None
                    }

                # Then add/override with separate PP page entries (more detailed)
                for entry in current_race_entries:
                    all_entries[entry['program_number']] = entry

                current_race['entries'] = list(all_entries.values())
                races_data.append(current_race)
                logger.info(f"Found race {current_race['race_number']} with {len(current_race['entries'])} entries")

            # If we only have Race 1 entries and no other races
            elif len(race_1_entries) > 0:
                race_1 = {
                    'race_number': 1,
                    'post_time': None,
                    'race_type': None,
                    'surface': 'Dirt',
                    'distance': None,
                    'distance_feet': None,
                    'purse': None,
                    'conditions': None,
                    'entries': race_1_entries
                }
                races_data.append(race_1)
                logger.info(f"Found race 1 with {len(race_1_entries)} entries")

            logger.info(f"Total races found: {len(races_data)}")

            # Insert races into database
            total_entries = 0
            successful_races = 0

            for race_data in races_data:
                race_id = insert_race_to_db(
                    supabase,
                    race_data,
                    track_id,
                    metadata['track_code'],
                    metadata['race_date'],
                    pdf_path
                )

                if race_id and race_data.get('entries'):
                    entries_count = insert_entries_to_db(supabase, race_id, race_data['entries'])
                    total_entries += entries_count
                    successful_races += 1
                    logger.info(f"Inserted race {race_data['race_number']} with {entries_count} entries")

            return {
                'success': True,
                'races_count': successful_races,
                'entries_count': total_entries,
                'track_code': metadata['track_code'],
                'race_date': metadata['race_date']
            }

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def parse_drf_pdf_safe(pdf_path: str, upload_log_id: Optional[str] = None) -> Dict:
    """
    Safe wrapper for parse_drf_pdf with error handling and logging
    """
    try:
        result = parse_drf_pdf(pdf_path, upload_log_id)
        return result
    except Exception as e:
        logger.error(f"Unexpected error in parse_drf_pdf_safe: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


# ==========================================
# COMMAND LINE INTERFACE
# ==========================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 parse_drf.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"Parsing DRF PDF: {pdf_path}")
    print("=" * 60)

    result = parse_drf_pdf_safe(pdf_path)

    print("\nResult:")
    print(f"  Success: {result['success']}")

    if result['success']:
        print(f"  Races parsed: {result['races_count']}")
        print(f"  Entries parsed: {result['entries_count']}")
        print(f"  Track: {result.get('track_code')}")
        print(f"  Date: {result.get('race_date')}")
    else:
        print(f"  Error: {result.get('error')}")
