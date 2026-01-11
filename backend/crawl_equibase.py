"""
Equibase Crawler for Historical Race Data
Crawls Equibase race chart PDFs and inserts results into Supabase database
Uses local Python parsing - NO API COSTS!
"""

import os
import sys
import logging
import time
import re
import requests
import pdfplumber
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from supabase_client import get_supabase_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common US tracks (expand as needed)
COMMON_TRACKS = [
    'AQU', 'BEL', 'CD', 'DMR', 'FG', 'GP', 'HOU', 'KEE', 'SA', 'SAR',
    'TAM', 'WO', 'MD', 'PRX', 'PIM'
]


def build_equibase_url(track_code: str, race_date: date, race_number: int) -> str:
    """
    Build Equibase PDF URL for a specific race
    Format: https://www.equibase.com/static/chart/pdf/TTMMDDYYUSAN.pdf

    Example: GP on 01/04/2024, Race 1 -> https://www.equibase.com/static/chart/pdf/GP010424USA1.pdf
    """
    mm = race_date.strftime('%m')
    dd = race_date.strftime('%d')
    yy = race_date.strftime('%y')

    url = f"https://www.equibase.com/static/chart/pdf/{track_code}{mm}{dd}{yy}USA{race_number}.pdf"
    return url


def download_pdf(pdf_url: str, timeout: int = 30) -> Optional[bytes]:
    """
    Download PDF from Equibase
    Returns: PDF bytes or None if download fails
    """
    try:
        logger.info(f"Downloading PDF from {pdf_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(pdf_url, headers=headers, timeout=timeout)

        if response.status_code == 200:
            logger.info(f"Successfully downloaded PDF ({len(response.content)} bytes)")
            return response.content
        else:
            logger.warning(f"PDF download failed with status {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading PDF: {e}")
        return None


def parse_equibase_pdf(pdf_bytes: bytes) -> Optional[Dict]:
    """
    Parse Equibase race chart PDF using pdfplumber
    Returns: Extracted race data or None if parsing fails
    """
    try:
        if not pdf_bytes.startswith(b'%PDF'):
            logger.warning("Downloaded content is not a valid PDF (likely HTML placeholder)")
            return None

        pdf_file = BytesIO(pdf_bytes)

        with pdfplumber.open(pdf_file) as pdf:
            if len(pdf.pages) == 0:
                logger.error("PDF has no pages")
                return None

            # Extract text from first page
            page = pdf.pages[0]
            text = page.extract_text()

            if not text:
                logger.error("Could not extract text from PDF")
                return None

            logger.debug(f"Extracted {len(text)} characters from PDF")

            # Parse the race data
            race_data = parse_race_chart_text(text)

            # Try to extract table data for horses
            tables = page.extract_tables()
            horses = []
            if tables:
                logger.info(f"Found {len(tables)} tables in PDF")
                horses = parse_horse_table(tables, text)
            
            # Fallback to text parsing if table method failed
            if not horses:
                logger.info("No horses found in tables, attempting text fallback parsing")
                horses = parse_horses_from_text(text)
                
            if horses:
                race_data['horses'] = horses

            return race_data

    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        return None


def parse_race_chart_text(text: str) -> Dict:
    """
    Parse race metadata from chart text
    """
    data = {
        'track_name': None,
        'race_date': None,
        'race_number': None,
        'post_time': None,
        'surface': None,
        'distance': None,
        'race_type': None,
        'conditions': None,
        'purse': None,
        'final_time': None,
        'fractional_times': [],
        'horses': [],
        'exotic_payouts': []
    }

    lines = text.split('\n')

    # Extract track name (usually on first line)
    if lines:
        data['track_name'] = lines[0].strip()

    # Extract race number
    race_num_match = re.search(r'RACE\s+(\d+)', text, re.IGNORECASE)
    if race_num_match:
        data['race_number'] = int(race_num_match.group(1))
    else:
        # Try alternate format
        race_num_match = re.search(r'Race\s*#?\s*(\d+)', text, re.IGNORECASE)
        if race_num_match:
            data['race_number'] = int(race_num_match.group(1))

    # Extract date
    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
    if date_match:
        data['race_date'] = date_match.group(1)

    # Extract post time
    time_match = re.search(r'POST TIME:\s*(\d{1,2}:\d{2})', text, re.IGNORECASE)
    if time_match:
        data['post_time'] = time_match.group(1)

    # Extract surface
    for keyword in ['Dirt', 'Turf', 'All Weather', 'Synthetic']:
        if keyword in text:
            data['surface'] = keyword
            break

    # Extract distance
    dist_match = re.search(r'(\d+\s*(?:Furlongs?|Miles?|Yards?))', text, re.IGNORECASE)
    if dist_match:
        data['distance'] = dist_match.group(1)
    else:
        # Try fractional distance
        dist_match = re.search(r'(\d+\s*1/\d+\s*(?:Miles?|Furlongs?))', text, re.IGNORECASE)
        if dist_match:
            data['distance'] = dist_match.group(1)

    # Extract purse
    purse_match = re.search(r'PURSE[:\s]+\$?([\d,]+)', text, re.IGNORECASE)
    if purse_match:
        data['purse'] = f"${purse_match.group(1)}"

    # Extract race type
    for race_type in ['Claiming', 'Allowance', 'Maiden', 'Stakes', 'Handicap']:
        if race_type.lower() in text.lower():
            data['race_type'] = race_type
            break

    # Extract final time
    time_match = re.search(r'FINAL TIME:\s*(\d+:\d+\.\d+)', text, re.IGNORECASE)
    if time_match:
        data['final_time'] = time_match.group(1)

    # Extract fractional times
    frac_match = re.findall(r'(\d+\.\d+)', text)
    if len(frac_match) > 0:
        # Filter to reasonable fractional times (between 20-70 seconds usually)
        data['fractional_times'] = [t for t in frac_match if 20.0 < float(t) < 70.0][:4]

    return data


def parse_horse_table(tables: List, full_text: str) -> List[Dict]:
    """
    Parse horse entries from extracted PDF tables
    """
    horses = []

    # Find the largest table (usually the results table)
    if not tables:
        return horses

    main_table = max(tables, key=lambda t: len(t) if t else 0)

    if not main_table or len(main_table) < 2:
        logger.warning("No valid table found for horses")
        return horses

    # Try to identify columns
    header_row = main_table[0] if main_table else []
    logger.debug(f"Table header: {header_row}")

    # Process each row
    for row_idx, row in enumerate(main_table[1:], start=1):
        if not row or len(row) < 3:
            continue

        try:
            horse_data = {
                'program_number': str(row[0]).strip() if row[0] else str(row_idx),
                'horse_name': str(row[1]).strip() if len(row) > 1 and row[1] else None,
                'jockey': str(row[2]).strip() if len(row) > 2 and row[2] else None,
                'trainer': str(row[3]).strip() if len(row) > 3 and row[3] else None,
                'owner': None,
                'weight': None,
                'odds': str(row[4]).strip() if len(row) > 4 and row[4] else None,
                'finish_position': row_idx,  # Assume order is finish position
                'comments': None,
                'speed_figure': None,
                'win_payout': None,
                'place_payout': None,
                'show_payout': None
            }

            # Clean up horse name
            if horse_data['horse_name']:
                horse_data['horse_name'] = re.sub(r'[^\w\s\'-]', '', horse_data['horse_name'])

            if horse_data['horse_name']:
                horses.append(horse_data)

        except Exception as e:
            logger.debug(f"Error parsing row {row_idx}: {e}")
            continue

    logger.info(f"Parsed {len(horses)} horses from table")
    return horses


def parse_horses_from_text(text: str) -> List[Dict]:
    """
    Fallback parser for horse data from raw text when table extraction fails
    Expects format: LastRaced Pgm HorseName(Jockey) ...
    """
    horses = []
    lines = text.split('\n')
    
    start_parsing = False
    
    # Regex to capture: Pgm, HorseName, Jockey, (skip), Odds
    # Example: 20Nov255AQU2 1 Coquito(Carmouche,Kendrick) 123 Lb ... 0.48* chased3w,edgedclear
    # We look for Pgm (number), Name(Jockey), and Odds (decimal at end)
    pattern = re.compile(r'^\s*\S+\s+(\d+)\s+([^(]+)\(([^)]+)\).*?(\d+\.\d+\*?)\s+')
    
    for line in lines:
        # Detect header
        if 'HorseName(Jockey)' in line or 'Horse Name (Jockey)' in line:
            start_parsing = True
            continue
            
        if not start_parsing:
            continue
            
        # Stop parsing if we hit other sections
        if 'Fractional Times' in line or 'Final Time' in line or 'Run-Up' in line or line.strip() == '':
            if len(horses) > 0: # If we already found horses, stop
                break
        
        match = re.search(pattern, line)
        if match:
            try:
                pgm = match.group(1)
                horse_name = match.group(2).strip()
                jockey = match.group(3).strip()
                odds = match.group(4).replace('*', '')
                
                horses.append({
                    'program_number': pgm,
                    'horse_name': horse_name,
                    'jockey': jockey,
                    'trainer': None, # Difficult to parse from this line
                    'owner': None,
                    'weight': None,
                    'odds': odds,
                    'finish_position': len(horses) + 1,
                    'comments': None,
                    'speed_figure': None,
                    'win_payout': None,
                    'place_payout': None,
                    'show_payout': None
                })
            except Exception as e:
                logger.debug(f"Regex match error on line '{line}': {e}")
                continue

    logger.info(f"Parsed {len(horses)} horses from text fallback")
    return horses


def parse_exotic_payouts(text: str) -> List[Dict]:
    """
    Extract exotic wager payouts from chart text
    """
    payouts = []

    # Common exotic bet patterns
    patterns = {
        'Exacta': r'EXACTA.*?\$?([\d,]+\.\d{2})',
        'Trifecta': r'TRIFECTA.*?\$?([\d,]+\.\d{2})',
        'Superfecta': r'SUPERFECTA.*?\$?([\d,]+\.\d{2})',
        'Daily Double': r'DAILY DOUBLE.*?\$?([\d,]+\.\d{2})',
        'Pick 3': r'PICK 3.*?\$?([\d,]+\.\d{2})',
        'Pick 4': r'PICK 4.*?\$?([\d,]+\.\d{2})',
    }

    for wager_type, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            payouts.append({
                'wager_type': wager_type,
                'payout': float(match.group(1).replace(',', '')),
                'winning_combination': None  # Would need more parsing
            })

    return payouts


def extract_race_from_pdf(pdf_url: str, max_retries: int = 3) -> Optional[Dict]:
    """
    Extract race data from Equibase PDF using local parsing
    Returns: Extracted race data or None if extraction fails
    """
    for attempt in range(1, max_retries + 1):
        logger.info(f"Extracting data from {pdf_url} (attempt {attempt}/{max_retries})")

        # Download PDF
        pdf_bytes = download_pdf(pdf_url)
        if not pdf_bytes:
            logger.warning(f"Extraction attempt {attempt} failed: Could not download PDF")
            if attempt < max_retries:
                time.sleep(2 * attempt)  # Exponential backoff
            continue

        # Parse PDF
        race_data = parse_equibase_pdf(pdf_bytes)
        if race_data and race_data.get('horses'):
            logger.info(f"Successfully extracted race with {len(race_data['horses'])} horses")
            return race_data
        else:
            logger.warning(f"Extraction attempt {attempt} failed: Could not parse race data")
            if attempt < max_retries:
                time.sleep(2 * attempt)

    logger.error(f"All extraction attempts failed for {pdf_url}")
    return None


def get_or_create_track(supabase, track_code: str, track_name: str = None) -> Optional[int]:
    """Get track ID or create if doesn't exist"""
    try:
        # Try to find existing track
        result = supabase.table('hranalyzer_tracks').select('id').eq('track_code', track_code).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]['id']

        # Create new track
        new_track = {
            'track_code': track_code,
            'track_name': track_name or track_code,
            'location': None,
            'timezone': 'America/New_York'
        }

        result = supabase.table('hranalyzer_tracks').insert(new_track).execute()
        if result.data:
            logger.info(f"Created new track: {track_code}")
            return result.data[0]['id']

        return None

    except Exception as e:
        logger.error(f"Error getting/creating track: {e}")
        return None


def insert_race_to_db(supabase, track_code: str, race_date: date, race_data: Dict) -> bool:
    """
    Insert crawled race data into Supabase
    Returns: True if successful, False otherwise
    """
    try:
        # Get or create track
        track_id = get_or_create_track(supabase, track_code, race_data.get('track_name'))
        if not track_id:
            logger.error(f"Could not get track_id for {track_code}")
            return False

        # Build race key
        race_number = race_data.get('race_number', 1)
        race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{race_number}"

        # Check if race already exists
        existing = supabase.table('hranalyzer_races').select('id').eq('race_key', race_key).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"Race {race_key} already exists, updating...")
            race_id = existing.data[0]['id']
            update_mode = True
        else:
            update_mode = False

        # Prepare race data
        race_insert = {
            'race_key': race_key,
            'track_id': track_id,
            'track_code': track_code,
            'track_name': race_data.get('track_name', track_code),
            'race_date': race_date.strftime('%Y-%m-%d'),
            'race_number': race_number,
            'post_time': race_data.get('post_time'),
            'surface': race_data.get('surface'),
            'distance': race_data.get('distance'),
            'race_type': race_data.get('race_type'),
            'conditions': race_data.get('conditions'),
            'purse': race_data.get('purse'),
            'final_time': race_data.get('final_time'),
            'fractional_times': ', '.join(race_data.get('fractional_times', [])) if race_data.get('fractional_times') else None,
            'race_status': 'completed',
            'data_source': 'equibase',
            'equibase_pdf_url': build_equibase_url(track_code, race_date, race_number),
            'equibase_chart_url': f"https://www.equibase.com/premium/eqbChartfrmUS.cfm?track={track_code}&racedate={race_date.strftime('%m/%d/%Y')}&racenumber={race_number}"
        }

        # Insert or update race
        if update_mode:
            result = supabase.table('hranalyzer_races').update(race_insert).eq('id', race_id).execute()
        else:
            result = supabase.table('hranalyzer_races').insert(race_insert).execute()
            if result.data:
                race_id = result.data[0]['id']

        logger.info(f"{'Updated' if update_mode else 'Inserted'} race {race_key}")

        # Insert horses and entries
        horses_data = race_data.get('horses', [])
        if horses_data:
            for horse_data in horses_data:
                insert_horse_entry(supabase, race_id, horse_data)

        # Insert exotic payouts
        payouts = race_data.get('exotic_payouts', [])
        if payouts:
            for payout in payouts:
                insert_exotic_payout(supabase, race_id, payout)

        return True

    except Exception as e:
        logger.error(f"Error inserting race to database: {e}")
        return False


def insert_horse_entry(supabase, race_id: int, horse_data: Dict):
    """Insert horse and race entry"""
    try:
        horse_name = horse_data.get('horse_name')
        if not horse_name:
            return

        # Get or create horse
        horse_result = supabase.table('hranalyzer_horses').select('id').eq('name', horse_name).execute()

        if horse_result.data and len(horse_result.data) > 0:
            horse_id = horse_result.data[0]['id']
        else:
            # Create horse
            new_horse = {'name': horse_name}
            horse_insert = supabase.table('hranalyzer_horses').insert(new_horse).execute()
            if horse_insert.data:
                horse_id = horse_insert.data[0]['id']
            else:
                logger.error(f"Could not create horse: {horse_name}")
                return

        # Create race entry
        entry_data = {
            'race_id': race_id,
            'horse_id': horse_id,
            'program_number': horse_data.get('program_number'),
            'finish_position': horse_data.get('finish_position'),
            'jockey_id': horse_data.get('jockey'),
            'trainer_id': horse_data.get('trainer'),
            'final_odds': horse_data.get('odds'),
            'win_payout': horse_data.get('win_payout'),
            'place_payout': horse_data.get('place_payout'),
            'show_payout': horse_data.get('show_payout'),
            'run_comments': horse_data.get('comments'),
            'weight': horse_data.get('weight')
        }

        supabase.table('hranalyzer_race_entries').insert(entry_data).execute()
        logger.debug(f"Inserted entry for horse {horse_name}")

    except Exception as e:
        logger.error(f"Error inserting horse entry: {e}")


def insert_exotic_payout(supabase, race_id: int, payout_data: Dict):
    """Insert exotic payout"""
    try:
        payout_insert = {
            'race_id': race_id,
            'wager_type': payout_data.get('wager_type'),
            'winning_combination': payout_data.get('winning_combination'),
            'payout': payout_data.get('payout')
        }

        supabase.table('hranalyzer_exotic_payouts').insert(payout_insert).execute()
        logger.debug(f"Inserted {payout_data.get('wager_type')} payout")

    except Exception as e:
        logger.error(f"Error inserting exotic payout: {e}")


def crawl_historical_races(target_date: date, tracks: List[str] = None) -> Dict:
    """
    Crawl historical races for a specific date

    Args:
        target_date: Date to crawl (usually yesterday)
        tracks: List of track codes to check (default: COMMON_TRACKS)

    Returns:
        Dict with crawl statistics
    """
    if tracks is None:
        tracks = COMMON_TRACKS

    logger.info(f"Starting crawl for {target_date}")
    logger.info(f"Tracks to check: {', '.join(tracks)}")

    supabase = get_supabase_client()

    stats = {
        'date': target_date.strftime('%Y-%m-%d'),
        'tracks_checked': len(tracks),
        'tracks_with_races': 0,
        'races_found': 0,
        'races_inserted': 0,
        'races_failed': 0
    }

    for track_code in tracks:
        logger.info(f"\nProcessing track: {track_code}")

        track_had_races = False
        race_num = 1

        # Try up to 12 races per track
        while race_num <= 12:
            pdf_url = build_equibase_url(track_code, target_date, race_num)

            # Extract race data
            race_data = extract_race_from_pdf(pdf_url, max_retries=2)

            if not race_data or not race_data.get('horses'):
                if race_num == 1:
                    logger.info(f"No race 1 found at {track_code}, moving to next track")
                else:
                    logger.info(f"No more races found at {track_code} after race {race_num-1}")
                break

            # Mark that this track had races
            if not track_had_races:
                track_had_races = True
                stats['tracks_with_races'] += 1

            stats['races_found'] += 1

            # Insert to database
            success = insert_race_to_db(supabase, track_code, target_date, race_data)
            if success:
                stats['races_inserted'] += 1
                logger.info(f"✓ Successfully processed {track_code} Race {race_num}")
            else:
                stats['races_failed'] += 1
                logger.error(f"✗ Failed to insert {track_code} Race {race_num}")

            race_num += 1
            time.sleep(1)  # Be polite to Equibase servers

    logger.info("\n" + "="*80)
    logger.info("Crawl Summary:")
    logger.info(f"  Date: {stats['date']}")
    logger.info(f"  Tracks checked: {stats['tracks_checked']}")
    logger.info(f"  Tracks with races: {stats['tracks_with_races']}")
    logger.info(f"  Races found: {stats['races_found']}")
    logger.info(f"  Races inserted: {stats['races_inserted']}")
    logger.info(f"  Races failed: {stats['races_failed']}")
    logger.info("="*80 + "\n")

    return stats


if __name__ == "__main__":
    from datetime import timedelta

    # Default to yesterday
    target = date.today() - timedelta(days=1)

    # Or specify date via command line
    if len(sys.argv) > 1:
        try:
            target = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    logger.info(f"Starting Equibase crawler for {target}")
    stats = crawl_historical_races(target)

    if stats['races_inserted'] > 0:
        logger.info(f"✓ Crawl completed successfully!")
        sys.exit(0)
    else:
        logger.error(f"✗ Crawl completed with no races inserted")
        sys.exit(1)
