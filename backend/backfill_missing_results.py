from curl_cffi import requests
import logging
from datetime import datetime, timedelta
from crawl_equibase import parse_equibase_full_card, insert_race_to_db
from supabase_client import get_supabase_client
import sys
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_date(track_code, target_date):
    """
    Backfill a specific track-date using the premium PDF endpoint
    """
    date_str = target_date.strftime('%m/%d/%Y') # Format: 01/09/2026
    
    # Premium PDF URL format
    url = f"https://www.equibase.com/premium/eqbPDFChartPlus.cfm?RACE=A&BorP=P&TID={track_code}&CTRY=USA&DT={date_str}&DAY=D&STYLE=EQB"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Referer': 'https://www.equibase.com/'
    }
    
    logger.info(f"Downloading Full Card PDF for {track_code} on {date_str} via curl_cffi...")
    try:
        r = requests.get(url, headers=headers, impersonate="chrome", timeout=60)
        if r.status_code != 200 or not r.content.startswith(b'%PDF'):
            logger.error(f"Failed to download PDF for {track_code} {date_str}. Status: {r.status_code}")
            return False
        
        logger.info(f"Downloaded PDF ({len(r.content)} bytes). Parsing...")
        races = parse_equibase_full_card(r.content)
        
        if not races:
            logger.warning(f"No races found in PDF for {track_code} {date_str}")
            return False
            
        logger.info(f"Found {len(races)} races. Saving to database...")
        supabase = get_supabase_client()
        
        for race_data in races:
            # Add track_code if missing
            race_data['track_code'] = track_code
            # insert_race_to_db(supabase, track_code, race_date, race_data, race_number=None)
            from datetime import date as date_obj
            insert_race_to_db(supabase, track_code, target_date.date(), race_data, race_data.get('race_number'))
            
        logger.info(f"Successfully processed {len(races)} races for {track_code} {date_str}")
        return True
        
    except Exception as e:
        logger.error(f"Error backfilling {track_code} {date_str}: {e}")
        return False

def run_backfill():
    # Target dates from investigation
    missing_dates = [
        datetime(2026, 1, 2),
        datetime(2026, 1, 5),
        datetime(2026, 1, 6),
        datetime(2026, 1, 7),
        datetime(2026, 1, 8),
        datetime(2026, 1, 9),
        datetime(2026, 1, 10),
        datetime(2026, 1, 11),
        datetime(2026, 1, 12),
        datetime(2026, 1, 13),
        datetime(2026, 1, 14)
    ]
    
    track = "GP" # Gulfstream Park
    
    for d in missing_dates:
        success = backfill_date(track, d)
        if success:
            logger.info(f"Successfully backfilled {d.date()}")
        else:
            logger.warning(f"Failed to backfill {d.date()}")
        
        # Sleep to avoid hitting limits
        time.sleep(2)

if __name__ == "__main__":
    # If args provided, backfill specific date
    if len(sys.argv) > 1:
        date_str = sys.argv[1] # YYYY-MM-DD
        track = sys.argv[2] if len(sys.argv) > 2 else "GP"
        d = datetime.strptime(date_str, '%Y-%m-%d')
        backfill_date(track, d)
    else:
        run_backfill()
