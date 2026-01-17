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
import subprocess
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


def normalize_name(name: str) -> str:
    """
    Normalize name for more reliable mapping (strip non-alphanumeric, lowercase)
    """
    if not name:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()


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


def download_pdf(pdf_url: str, timeout: int = 40) -> Optional[bytes]:
    """
    Download PDF from Equibase using PowerShell with robust browser masquerading to bypass WAF
    Returns: PDF bytes or None if download fails
    """
    temp_file = f"temp_pdf_{int(time.time())}_{os.getpid()}.pdf"
    
    try:
        logger.info(f"Downloading PDF from {pdf_url} via PowerShell")
        
        # Comprehensive headers to mimic Chrome on Windows exactly
        # Note: PowerShell escaping with backticks ` or using a Headers hash
        
        ps_script = f"""
        $headers = @{{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            "Accept" = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            "Accept-Language" = "en-US,en;q=0.9"
            "Referer" = "https://www.equibase.com/"
            "Sec-Ch-Ua" = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            "Sec-Ch-Ua-Mobile" = "?0"
            "Sec-Ch-Ua-Platform" = '"Windows"'
            "Sec-Fetch-Dest" = "document"
            "Sec-Fetch-Mode" = "navigate"
            "Sec-Fetch-Site" = "same-origin"
            "Sec-Fetch-User" = "?1"
            "Upgrade-Insecure-Requests" = "1"
        }}
        
        try {{
            Invoke-WebRequest -Uri '{pdf_url}' -OutFile '{temp_file}' -Headers $headers -TimeoutSec {timeout} -ErrorAction Stop
        }} catch {{
            Write-Host "Error: $($_.Exception.Message)"
            exit 1
        }}
        """
        
        # Execute PowerShell
        # -NoProfile -NonInteractive -ExecutionPolicy Bypass
        cmd = [
            "powershell", 
            "-NoProfile",
            "-NonInteractive", 
            "-ExecutionPolicy", "Bypass", 
            "-Command", 
            ps_script
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        
        # Check if file exists and has size
        # Check if file exists and has size
        if os.path.exists(temp_file):
            size = os.path.getsize(temp_file)
            if size < 2000: # 2KB is too small for a PDF chart
                # Read content to see if it's a 404 or Block
                with open(temp_file, 'rb') as f:
                    content_head = f.read(1000)
                
                check_str = content_head.decode('utf-8', errors='ignore').lower()
                
                if "404" in check_str or "not found" in check_str or "unavailable" in check_str:
                     logger.warning(f"PDF not found (404) at {pdf_url}. Chart likely not generated yet.")
                else:
                     logger.warning(f"Downloaded file too small ({size} bytes). Likely blocked by WAF.")

                return None
            
            # Validation: check first bytes
            with open(temp_file, 'rb') as f:
                head = f.read(4)
            if head != b'%PDF':
                logger.warning("File header is not %PDF. Discarding.")
                return None
            
            with open(temp_file, 'rb') as f:
                content = f.read()
                
            logger.info(f"Successfully downloaded PDF ({len(content)} bytes)")
            return content
        else:
            logger.warning(f"PowerShell download failed or file not created.")
            return None

    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        return None
        
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


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
                # Merge WPS Payouts if available
                wps_payouts = race_data.get('wps_payouts', {})
                
                # Merge Trainers from footer if missing (common in text fallback)
                trainers_map = parse_trainers_section(text)
                
                for horse in horses:
                    pgm = horse.get('program_number')
                    
                    # Merge WPS
                    if pgm and pgm in wps_payouts:
                        payout = wps_payouts[pgm]
                        horse['win_payout'] = payout.get('win')
                        horse['place_payout'] = payout.get('place')
                        horse['show_payout'] = payout.get('show')
                    
                    # Merge Trainer if missing
                    if not horse.get('trainer') and pgm and pgm in trainers_map:
                         horse['trainer'] = trainers_map[pgm]
                         logger.debug(f"Merged trainer {horse['trainer']} for horse {pgm}")

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
        'exotic_payouts': [],
        'wps_payouts': parse_wps_payouts(text),
        'exotic_payouts': [],
        'wps_payouts': parse_wps_payouts(text),
        'claims': [],
        'scratches': parse_scratched_horses(text)
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
    # More flexible regex to catch cases without colons, different separators, or missing spaces
    # Fix for cases like "Final Time : 1:44.23" or "Final Time: 1:44.23"
    time_match = re.search(r'FINAL\s*TIME\s*:?\s*([\d:.]+)', text, re.IGNORECASE)
    if time_match:
        data['final_time'] = time_match.group(1).strip()

    # Extract fractional times
    frac_match = re.findall(r'(\d+\.\d+)', text)
    if len(frac_match) > 0:
        # Filter to reasonable fractional times (between 20-70 seconds usually)
        data['fractional_times'] = [t for t in frac_match if 20.0 < float(t) < 70.0][:4]

    # Extract claims
    data['claims'] = parse_claims_text(text)

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
            
            # Helper to merge WPS if available
            # Note: We can't access race_data here directly easily unless we pass it or pass payouts map
            # TODO: We need to refactor parse_horse_table signature or do the merge later.
            # Actually, let's fix the call site, but for now we need to enable "payouts" arg in this function?
            # Or we can do it after this function returns in parse_equibase_pdf
            # Let's check parse_equibase_pdf again.


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


def parse_wps_payouts(text: str) -> Dict[str, Dict[str, float]]:
    """
    Parse Win/Place/Show payouts from the 'Mutuel Prices' or 'Payoffs' section
    Returns: Dict mapping Program Number -> {'win': float, 'place': float, 'show': float}
    """
    payouts = {}
    
    # 1. Find the start of the section
    # Usually "Total WPS Pool" or headers "Pgm Horse Win Place Show"
    lines = text.split('\n')
    start_idx = -1
    
    header_pattern = re.compile(r'Pgm\s+Horse\s+Win\s+Place\s+Show', re.IGNORECASE)
    
    for i, line in enumerate(lines):
        if header_pattern.search(line):
            start_idx = i + 1
            break
            
    if start_idx == -1:
        # Try finding "Total WPS Pool" then look ahead a line or two
        pool_pattern = re.compile(r'Total\s+WPS\s+Pool', re.IGNORECASE)
        for i, line in enumerate(lines):
            if pool_pattern.search(line):
                # Header usually follows or is nearby
                # Scan next few lines for header? Or assuming next lines are data if header is missing/implicit
                # Let's try to assume data follows immediately after header row found by context
                pass # Logic difficult without consistent header, but header is standard on Equibase
    
    if start_idx == -1:
        logger.debug("Could not find WPS Payouts section header")
        return payouts
        
    # 2. Parse the rows following the header
    # We expect rows roughly ordered by finish position:
    # Row 1 (Winner): Pgm Name Win Place Show
    # Row 2 (Place): Pgm Name Place Show
    # Row 3 (Show): Pgm Name Show
    
    # Regex to extract: Pgm (digits/char), Horse Name (text), Floats...
    # The complexity is that Horse Name can contain spaces.
    # But Pgm is at start, and floats are at end (sort of, WagerType might follow).
    
    # Strategy: Find all prices (Pattern: \d+\.\d{2})
    # Then everything before the first price is Pgm + Horse Name
    
    current_row_idx = 0 # 0=Win/Place/Show, 1=Place/Show, 2=Show
    
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
            
        # Stop condition: Section end? 
        # Usually followed by "Past Performance" or "Footnotes" or empty lines
        if "Past Performance" in line or "Footnotes" in line or "Trainers:" in line:
            break
            
        # Stop if we hit Exotics (sometimes on same line, sometimes next)
        # Actually in the screenshot, "Wager Type" is on the SAME LINE as the first horse
        # But `extract_text` might separate them or keep them.
        # We process the line assuming it effectively starts with Pgm ... Prices
        
        # Regex for prices: look for numbers like "15.60"
        # Note: sometimes they are just "4.20"
        prices = re.findall(r'(\d+\.\d{2})', line)
        
        if not prices:
            continue
            
        # Pgm is usually the first token
        parts = line.split()
        if not parts:
            continue
            
        pgm = parts[0]
        
        # Validate Pgm is somewhat short (e.g. "1", "1A", "10")
        if len(pgm) > 4: 
            continue
            
        # Map prices based on row index logic
        # Note: This is a heuristics based on standard Finish Order sorting in the table
        
        win_val = None
        place_val = None
        show_val = None
        
        # Extract potential prices. 
        # We need to distinguish "Prices" from "Pools" or "Payoffs" of exotics if they appear on the same line.
        # In the screenshot: 
        # Line 1: 3 Daylan 15.60 8.00 5.00 $1.00 Exacta...
        # Prices are 15.60, 8.00, 5.00, 1.00 (wager), 125.80 (payoff)
        # We must take the FIRST 1, 2, or 3 prices that appear textually before "Wager Type" or end of line.
        
        # Refined regex: Split line by the first occurrence of known Wager Types? 
        # Or just take the first N floats found?
        # Usually Pgm Name P1 P2 P3 ...
        
        # Let's try to isolate the "WPS" part.
        # It ends before "Wager Type" column start.
        # But we don't know column positions in raw text.
        
        # Heuristic: 
        # - Row 0 (Winner): Expect 3 prices (Win, Place, Show). If fewer, maybe dead heat or missing data.
        # - Row 1 (Place): Expect 2 prices (Place, Show).
        # - Row 2 (Show): Expect 1 price (Show).
        
        # Filter prices to only those that look like WPS prices? No distinguishing feature.
        # Take the first k valid floats found in the line.
        
        try:
            # We assume the first found prices correspond to Win/Place/Show columns depending on row
            
            valid_prices = []
            # We iterate matches. We stop if we hit something that looks like an exotic bet amount (usually prefixed by $) or Wager Name
            # Actually, raw text might imply spatial separation.
            
            # Let's iterate tokens to be safer?
            # "3", "Daylan", "15.60", "8.00", "5.00", "$1.00", "Exacta"...
            
            # Find the index where prices start
            price_start_idx = -1
            found_prices = []
            
            tokens = line.split()
            for idx, token in enumerate(tokens):
                # skip pgm
                if idx == 0: continue
                
                # Check if price
                # handling "$15.60" or "15.60"
                clean_token = token.replace('$', '')
                if re.match(r'^\d+\.\d{2}$', clean_token):
                     found_prices.append(float(clean_token))
                elif token.startswith('$'): 
                     # Should be start of Wager Type section e.g. $1.00 Exacta
                     # Stop collecting prices
                     break
                elif re.match(r'Exacta|Trifecta|Superfecta|Daily|Pick', token, re.IGNORECASE):
                     break
            
            row_payouts = {'win': None, 'place': None, 'show': None}
            
            if current_row_idx == 0: # Winner row
                # Expect 3 prices (Win, Place, Show)
                if len(found_prices) >= 3:
                    row_payouts['win'] = found_prices[0]
                    row_payouts['place'] = found_prices[1]
                    row_payouts['show'] = found_prices[2]
                elif len(found_prices) == 2: # Maybe no show betting? Or Dead Heat?
                    row_payouts['win'] = found_prices[0]
                    row_payouts['place'] = found_prices[1]
                elif len(found_prices) == 1:
                    row_payouts['win'] = found_prices[0]
                    
            elif current_row_idx == 1: # Place row
                # Expect Place, Show
                if len(found_prices) >= 2:
                    row_payouts['place'] = found_prices[0]
                    row_payouts['show'] = found_prices[1]
                elif len(found_prices) == 1:
                    row_payouts['place'] = found_prices[0]
                    
            elif current_row_idx >= 2: # Show row(s)
                # Expect Show
                if len(found_prices) >= 1:
                    row_payouts['show'] = found_prices[0]
                    # Note: if there's a dead heat for 3rd, there might be multiple lines here
            
            if any(row_payouts.values()):
                payouts[pgm] = row_payouts
                current_row_idx += 1
                
        except Exception as e:
            logger.debug(f"Error parsing WPS line '{line}': {e}")
            continue
    return payouts



def parse_trainers_section(text: str) -> Dict[str, str]:
    """
    Parse Trainers section from text
    Example: Trainers: 3 - Handal, Raymond; 4 - Rice, Linda; ...
    """
    trainers = {}
    
    # Locate section
    # Regex: Trainers:\s*(.*?)(?:\s+Owners:|\s+Footnotes|\s+Scratched|$)
    match = re.search(r'Trainers:\s*(.*?)(?:\s+Owners:|\s+Footnotes|\s+Scratched|$)', text, re.IGNORECASE | re.DOTALL)
    
    if match:
        content = match.group(1).replace('\n', ' ').strip()
        # Split by semicolon
        # entry format: "Pgm - Name"
        entries = content.split(';')
        for entry in entries:
            entry = entry.strip()
            if not entry: continue
            
            # Split by " - " or just "-"
            parts = entry.split('-', 1)
            if len(parts) == 2:
                pgm = parts[0].strip()
                name = parts[1].strip()
                trainers[pgm] = name
            else:
                # Fallback: maybe space separated? "3 Handal, Raymond"
                # Check for first digit
                m = re.match(r'^(\d+)\s+(.+)', entry)
                if m:
                    trainers[m.group(1)] = m.group(2).strip()
                    
    return trainers


def parse_scratched_horses(text: str) -> List[str]:
    """
    Parse Scratched Horses section
    Example: Scratched Horse(s): Horse Name (Reason)
    """
    scratches = []
    # Regex: Scratched Horse(s):\s*(.*?)(?:\s+Trainers:|\s+Footnotes|$)
    match = re.search(r'Scratched\s*Horse\(s\)\s*:\s*(.*?)(?:\s+Trainers:|\s+Owner\(s\):|\s+Footnotes|\s+Claiming|$)', text, re.IGNORECASE | re.DOTALL)
    
    if match:
        content = match.group(1).replace('\n', ' ').strip()
        # Split by comma or semicolon
        # Example: "Horse A (Trainer); Horse B (Vet)"
        # Sometimes just commas. "Horse A (Re-entered), Horse B (Trainer)"
        
        # Split by closing parenthesis + comma/semicolon, or just comma
        # Splitting by comma is risky if names have commas (rare)
        # Assuming comma separator
        parts = re.split(r'[;,]\s*', content)
        
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # Remove reason in parens "(Trainer)"
            name = re.sub(r'\s*\(.*?\)', '', part).strip()
            if name:
                scratches.append(name)
                
    return scratches


def parse_claims_text(text: str) -> List[Dict]:
    """
    Parse claimed horses information
    Example: 1 Claimed Horse(s): Coquito New Trainer: Linda Rice New Owner: Linda Rice
    Also handles multi-line claims and split labels.
    """
    claims = []
    lines = text.split('\n')
    
    # 1. Parse Claiming Prices first to get price map
    price_map = {}
    
    # Flexible regex: Claiming\s*Prices\s*:
    price_match = re.search(r'Claiming\s*Prices\s*:(.*?)(?:Scratched|Total|Footnotes|$)', text, re.DOTALL | re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).strip()
        # Split by semicolon or just find all matches
        # Pattern: number - Name: $price (Allow space after $)
        price_items = re.findall(r'(\d+)\s*-\s*([^:]+):\s*\$\s*([\d,]+)', price_text)
        for num, name, price in price_items:
            # Normalize name
            norm_name = normalize_name(name)
            price_val = float(price.replace(',', ''))
            price_map[norm_name] = price_val
            logger.debug(f"Mapped '{name}' (norm: {norm_name}) to {price_val}")

    # 2. Parse Claimed Horse lines using robust state machine
    in_claims = False
    current_claim = None
    
    # Patterns
    # Note: (\s*) allows for no space if PDF extraction removed it
    trainer_pat = re.compile(r'\s*(?:New\s*Trainer|NewTrainer)\s*:\s*', re.IGNORECASE)
    owner_pat = re.compile(r'\s*(?:New\s*Owner|NewOwner)\s*:\s*', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Start detection
        if re.search(r'Claimed\s*Horse\(s\)\s*:', line, re.IGNORECASE):
            in_claims = True
            # Remove the prefix "N Claimed Horse(s):" to process the first line content
            line = re.sub(r'^\d*\s*Claimed\s*Horse\(s\)\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            
        if not in_claims: continue
        
        # End detection
        # Stop at ClaimingPrices, Scratched, Total, Fractional, Final Time, Run-Up match
        if re.match(r'(Claiming\s*Prices|Scratched|Total|Fractional|Final|Run-Up)', line, re.IGNORECASE):
            if current_claim: claims.append(current_claim)
            in_claims = False
            break
            
        # Process Line Logic
        # Check if line contains "New Trainer" -> Starts a new claim
        trainer_match = trainer_pat.search(line)
        
        if trainer_match:
            # Save previous claim if valid
            if current_claim: claims.append(current_claim)
            
            # This line starts a new claim
            # Format: "HorseName NewTrainer: TrainerName [NewOwner: OwnerName]"
            
            # Split at Trainer label
            start_idx = trainer_match.start()
            end_idx = trainer_match.end()
            
            horse_part = line[:start_idx].strip()
            rest = line[end_idx:].strip()
            
            # Now search for Owner in 'rest'
            owner_match = owner_pat.search(rest)
            
            if owner_match:
                # "TrainerName NewOwner: OwnerName"
                o_start = owner_match.start()
                o_end = owner_match.end()
                
                trainer_name = rest[:o_start].strip()
                owner_name = rest[o_end:].strip()
                
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': trainer_name,
                    'new_owner': owner_name,
                    'claim_price': None
                }
            else:
                # "TrainerName [maybe crap]" or partial line
                # Treat rest as trainer name provisionally
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': rest, 
                    'new_owner': ""
                }
        else:
            # No "New Trainer". Continuation line.
            if current_claim:
                # Identify if previous line ended with partial label like "NewOw"
                prev_trainer = current_claim['new_trainer']
                
                # Check for "NewOwner" reconstruction from split label
                if prev_trainer.endswith("NewOw") or prev_trainer.endswith("New"):
                     # Attempt to combine and re-check owner pattern
                     combined = prev_trainer + line
                     om = owner_pat.search(combined)
                     if om:
                         o_start = om.start()
                         o_end = om.end()
                         
                         real_trainer = combined[:o_start].strip()
                         real_owner = combined[o_end:].strip()
                         
                         current_claim['new_trainer'] = real_trainer
                         current_claim['new_owner'] = real_owner
                     else:
                         # Just append to owner if we already had one, or append to trainer?
                         # If we didn't have an owner, and this doesn't match owner pattern, it might be trailing trainer name?
                         if not current_claim['new_owner']:
                             current_claim['new_trainer'] += " " + line
                         else:
                             current_claim['new_owner'] += " " + line
                else:
                    # Normal continuation
                    if not current_claim['new_owner']:
                        # Maybe we missed the owner label or it's coming
                        # Or maybe the trainer name is long?
                        # Usually "New Owner" follows trainer.
                        # If we haven't seen New Owner label yet, and this line doesn't have it...
                        # Check if this line IS the owner label?
                        om = owner_pat.search(line)
                        if om:
                             o_end = om.end()
                             owner_name = line[o_end:].strip()
                             current_claim['new_owner'] = owner_name
                        else:
                             # Append to trainer
                             current_claim['new_trainer'] += " " + line
                    else:
                        # Append to owner
                        current_claim['new_owner'] += " " + line
                        current_claim['new_owner'] = current_claim['new_owner'].strip()

    # Final cleanup and pricing
    for c in claims:
        # Match price
        hn = normalize_name(c['horse_name'])
        price = price_map.get(hn)
        if not price:
            # Fuzzy match
            for k, v in price_map.items():
                if k in hn or hn in k:
                    price = v
                    break
        c['claim_price'] = price
        
        # Clean specific artifacts
        if c['new_owner']: c['new_owner'] = c['new_owner'].strip()
        if c['new_trainer']: c['new_trainer'] = c['new_trainer'].strip()

    return claims


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


def insert_race_to_db(supabase, track_code: str, race_date: date, race_data: Dict, race_number: int = None) -> bool:
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

        # Build race key - Priority: 1. Passed race_number, 2. Data from PDF, 3. Default 1
        if race_number is None:
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
            'race_date': race_date.strftime('%Y-%m-%d'),
            'race_number': race_number,
            # 'post_time': race_data.get('post_time'), # Handle conditionally below
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
            'equibase_chart_url': f"https://www.equibase.com/static/chart/pdf/{track_code}{race_date.strftime('%m%d%y')}USA{race_number}.pdf"
        }

        # Only update post_time if we actually found one
        if race_data.get('post_time'):
            race_insert['post_time'] = race_data.get('post_time')

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

        # Insert claims
        claims_data = race_data.get('claims', [])
        if claims_data:
            for claim in claims_data:
                insert_claim(supabase, race_id, claim)

        # Mark scratches
        scratches = race_data.get('scratches', [])
        if scratches:
            mark_scratched_horses(supabase, race_id, scratches)

        return True

    except Exception as e:
        logger.error(f"Error inserting race to database: {e}")
        return False


def get_or_create_participant(supabase, table_name: str, name_col: str, name_val: str) -> Optional[str]:
    """Generic helper to get or create a named entity (Jockey, Trainer, etc)"""
    try:
        # Check existing
        res = supabase.table(table_name).select('id').eq(name_col, name_val).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['id']
        
        # Create new
        new_record = {name_col: name_val}
        res = supabase.table(table_name).insert(new_record).execute()
        if res.data:
            return res.data[0]['id']
            
    except Exception as e:
        logger.error(f"Error in get_or_create_participant for {table_name}: {e}")
    return None


def insert_horse_entry(supabase, race_id: int, horse_data: Dict):
    """Insert horse and race entry"""
    try:
        horse_name = horse_data.get('horse_name')
        if not horse_name:
            return

        # Get or create horse
        horse_result = supabase.table('hranalyzer_horses').select('id').eq('horse_name', horse_name).execute()

        if horse_result.data and len(horse_result.data) > 0:
            horse_id = horse_result.data[0]['id']
        else:
            # Create horse
            new_horse = {'horse_name': horse_name}
            horse_insert = supabase.table('hranalyzer_horses').insert(new_horse).execute()
            if horse_insert.data:
                horse_id = horse_insert.data[0]['id']
            else:
                logger.error(f"Could not create horse: {horse_name}")
                return

        # Get/Create Jockey
        jockey_id = None
        jockey_name = horse_data.get('jockey')
        if jockey_name:
            jockey_id = get_or_create_participant(supabase, 'hranalyzer_jockeys', 'jockey_name', jockey_name)

        # Get/Create Trainer
        trainer_id = None
        trainer_name = horse_data.get('trainer')
        if trainer_name:
            trainer_id = get_or_create_participant(supabase, 'hranalyzer_trainers', 'trainer_name', trainer_name)

        # Create race entry
        entry_data = {
            'race_id': race_id,
            'horse_id': horse_id,
            'program_number': horse_data.get('program_number'),
            'finish_position': horse_data.get('finish_position'),
            'jockey_id': jockey_id,
            'trainer_id': trainer_id,
            'final_odds': horse_data.get('odds'),
            'win_payout': horse_data.get('win_payout'),
            'place_payout': horse_data.get('place_payout'),
            'show_payout': horse_data.get('show_payout'),
            'run_comments': horse_data.get('comments'),
            'weight': horse_data.get('weight')
        }

        try:
            # Use upsert to handle case where entries were pre-populated by DRF PDF upload
            # on_conflict specified to match unique constraint (race_id, program_number)
            supabase.table('hranalyzer_race_entries').upsert(entry_data, on_conflict='race_id, program_number').execute()
            logger.debug(f"Upserted entry for horse {horse_name}")
        except Exception as e:
            logger.error(f"Error upserting horse entry: {e}")

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


def insert_claim(supabase, race_id: int, claim_data: Dict):
    """Insert claim data"""
    try:
        claim_insert = {
            'race_id': race_id,
            'horse_name': claim_data.get('horse_name'),
            'new_trainer_name': claim_data.get('new_trainer'),
            'new_owner_name': claim_data.get('new_owner'),
            'claim_price': claim_data.get('claim_price')
        }
        
        # Use upsert to update existing claims (e.g. if price was missing)
        # Unique constraint is (race_id, horse_name)
        supabase.table('hranalyzer_claims').upsert(claim_insert, on_conflict='race_id, horse_name').execute()
        
        logger.info(f"Upserted claim for {claim_data.get('horse_name')} with price {claim_insert['claim_price']}")
        
    except Exception as e:
        logger.error(f"Error inserting/updating claim: {e}")


def mark_scratched_horses(supabase, race_id: int, scratched_names: List[str]):
    """
    Mark horses as scratched in the database
    """
    try:
        if not scratched_names:
            return

        # 1. Get all entries for this race to find program numbers/ids by name
        # We need to join with horses table to get names
        entries = supabase.table('hranalyzer_race_entries')\
            .select('id, program_number, hranalyzer_horses!inner(horse_name)')\
            .eq('race_id', race_id)\
            .execute()
            
        if not entries.data:
            return

        # 2. Match names
        for name in scratched_names:
            norm_scratch = normalize_name(name)
            
            for entry in entries.data:
                h_name = entry['hranalyzer_horses']['horse_name']
                norm_h = normalize_name(h_name)
                
                # Check match
                if norm_scratch in norm_h or norm_h in norm_scratch: 
                    # Set scratched=True
                    # We can update by ID directly
                    supabase.table('hranalyzer_race_entries')\
                        .update({'scratched': True, 'finish_position': None})\
                        .eq('id', entry['id'])\
                        .execute()
                    
                    logger.info(f"Marked {h_name} as scratched")
                    break
                    
    except Exception as e:
        logger.error(f"Error marking scratches: {e}")


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
        missing_consecutive = 0

        # Try up to 12 races per track
        while race_num <= 12:
            try:
                # Check if race is already completed in DB to avoid re-downloading
                race_key = f"{track_code}-{target_date.strftime('%Y%m%d')}-{race_num}"
                existing = supabase.table('hranalyzer_races').select('race_status').eq('race_key', race_key).execute()
                
                if existing.data and len(existing.data) > 0:
                    status = existing.data[0]['race_status']
                    if status == 'completed':
                        logger.info(f"Skipping {race_key} (Already Completed)")
                        race_num += 1
                        # If we found it in DB, we count it as "found" essentially, but maybe not for stats?
                        # Actually if we skip it, we might stop the loop if we rely on "race_data" being found?
                        # No, we just continue to next race. 
                        # BUT: if race 1 is completed, race 2 might not be.
                        # However, if race 1 is NOT found, we break.
                        # So we must NOT break here.
                        # We must mark track_had_races = True if we found a completed race too.
                        track_had_races = True
                        continue
            except Exception as e:
                logger.debug(f"Error checking status for {race_key}: {e}")

            pdf_url = build_equibase_url(track_code, target_date, race_num)

            # Extract race data
            race_data = extract_race_from_pdf(pdf_url, max_retries=2)

            if not race_data or not race_data.get('horses'):
                missing_consecutive += 1
                if missing_consecutive >= 3:
                    if race_num == 1:
                        logger.info(f"No race 1 found at {track_code}, moving to next track")
                    else:
                        logger.info(f"Stop searching {track_code} after {missing_consecutive} consecutive misses.")
                    break
                else:
                    logger.info(f"Race {race_num} at {track_code} not found. Skipping to check next (miss {missing_consecutive}/3)")
                    race_num += 1
                    continue
            
            # Reset missing count if we found a race
            missing_consecutive = 0

            # Mark that this track had races
            if not track_had_races:
                track_had_races = True
                stats['tracks_with_races'] += 1

            stats['races_found'] += 1

            # Insert to database
            success = insert_race_to_db(supabase, track_code, target_date, race_data, race_num)
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
