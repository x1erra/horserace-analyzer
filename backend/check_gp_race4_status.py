
import logging
import sys
import os
from datetime import date
from supabase_client import get_supabase_client
from crawl_scratches import fetch_rss_feed, parse_rss_changes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_gp_race4_status():
    track_code = 'GP'
    race_date = date.today()
    race_number = 4
    race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{race_number}"
    
    logger.info(f"Checking status for {race_key}...")
    
    # 1. Check DB
    supabase = get_supabase_client()
    res = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key).execute()
    
    if res.data:
        race = res.data[0]
        logger.info(f"DB Status: {race.get('race_status')}")
        logger.info(f"DB Record: {race}")
        
        # Check for results in hranalyzer_race_results if that table exists or where results are stored
        # Assuming results might be in hranalyzer_results or similar, checking schema would be good but let's check basic table first
    else:
        logger.warning("Race not found in DB!")
        return

    # Check Changes Table
    changes_res = supabase.table('hranalyzer_changes').select('*').eq('race_id', race['id']).execute()
    if changes_res.data:
        logger.info(f"DB Changes ({len(changes_res.data)}):")
        for c in changes_res.data:
             logger.info(f" - {c['change_type']}: {c['description']}")
    else:
        logger.info("No changes records in DB.")


    # 2. Check RSS Source
    logger.info(f"Fetching RSS for {track_code}...")
    xml = fetch_rss_feed(track_code)
    
    if xml:
        logger.info("RSS Feed Fetched successfully.")
        changes = parse_rss_changes(xml, track_code)
        
        # Filter for Race 4
        r4_changes = [c for c in changes if c['race_number'] == race_number]
        
        if r4_changes:
            logger.info(f"Found RSS changes for Race 4: {r4_changes}")
        else:
            logger.info("No changes found in RSS for Race 4.")
            
        print("\n--- RAW XML SEGMENT FOR RACE 4 (if any) ---")
        # dump simplified view
        for line in xml.split('\n'):
             if "Race 4" in line or "Race 04" in line:
                 print(line.strip())
    else:
        logger.warning("Failed to fetch RSS feed.")

if __name__ == "__main__":
    check_gp_race4_status()
