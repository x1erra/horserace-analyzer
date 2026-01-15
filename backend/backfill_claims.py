
import os
import sys
import logging
import time
from datetime import date, timedelta, datetime
from typing import List, Dict

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client
from crawl_equibase import extract_race_from_pdf, insert_race_to_db, build_equibase_url

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

def backfill_claims(start_date: date, end_date: date):
    supabase = get_supabase_client()
    
    logger.info(f"Starting backfill from {start_date} to {end_date}")
    
    # Iterate dates
    current = start_date
    while current <= end_date:
        logger.info(f"Processing date: {current}")
        
        # Get races for this date from DB to know what to check
        # Instead of blindly checking all tracks, checking known races is faster if we only care about existing ones.
        # BUT, if we missed races entirely, we should check tracks?
        # User asked to "backfill any past races claims". This implies correcting existing records.
        # If I want to be thorough, I should maybe just check all tracks?
        # But checking tracks is slow (many requests). Re-processing known races is faster.
        # Let's focus on races already in DB first.
        
        try:
            # Fetch races for this date
            # Note: race_date is date or string in DB? defined as date in python code.
            races = supabase.table('hranalyzer_races') \
                .select('track_code, race_number, id, race_key') \
                .eq('race_date', current.isoformat()) \
                .execute()
                
            if not races.data:
                logger.info(f"No races found in DB for {current}")
            else:
                logger.info(f"Found {len(races.data)} races for {current}")
                
                for race in races.data:
                    track_code = race['track_code']
                    race_num = race['race_number']
                    race_key = race['race_key']
                    
                    logger.info(f"Re-processing {race_key}...")
                    
                    # Construct URL
                    url = build_equibase_url(track_code, current, race_num)
                    
                    # Download & Parse
                    race_data = extract_race_from_pdf(url, max_retries=2)
                    
                    if race_data and race_data.get('horses'):
                        # Insert/Update
                        # This will update claims!
                        success = insert_race_to_db(supabase, track_code, current, race_data)
                        if success:
                            # Verify claims count
                            claims = race_data.get('claims', [])
                            logger.info(f"Updated {race_key} - Found {len(claims)} claims")
                        else:
                            logger.error(f"Failed to update DB for {race_key}")
                    else:
                        logger.warning(f"Failed to extract data for {race_key} during backfill")
                    
                    # Sleep slightly
                    time.sleep(0.5)
                    
        except Exception as e:
            logger.error(f"Error processing date {current}: {e}")
            
        current += timedelta(days=1)

if __name__ == "__main__":
    # Default: Jan 1 2026 to Today
    start = date(2026, 1, 1)
    end = date.today()
    
    if len(sys.argv) > 2:
        start = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        end = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
        
    backfill_claims(start, end)
