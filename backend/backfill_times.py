import os
import sys
import logging
from supabase_client import get_supabase_client
from crawl_equibase import extract_race_from_pdf, insert_race_to_db, COMMON_TRACKS
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_missing_times():
    """
    Finds completed races with missing final_time and attempts to re-crawl/parse them.
    """
    try:
        supabase = get_supabase_client()
        
        # 1. Find target races
        logger.info("Finding races with missing times...")
        res = supabase.table('hranalyzer_races')\
            .select('id, race_key, track_code, race_date, race_number, equibase_pdf_url')\
            .eq('race_status', 'completed')\
            .is_('final_time', 'null')\
            .execute()
            
        races = res.data
        if not races:
            logger.info("No races found with missing times.")
            return

        logger.info(f"Found {len(races)} races to backfill.")
        
        success_count = 0
        fail_count = 0

        for race in races:
            race_key = race['race_key']
            pdf_url = race['equibase_pdf_url']
            
            logger.info(f"Processing {race_key} - {pdf_url}")
            
            # 2. Extract data (using updated parser)
            if not pdf_url:
                logger.warning(f"No PDF URL for {race_key}, skipping.")
                fail_count += 1
                continue
                
            race_data = extract_race_from_pdf(pdf_url)
            
            if race_data and race_data.get('final_time'):
                logger.info(f"Found time: {race_data['final_time']}")
                
                # 3. Update DB
                # We can use insert_race_to_db which handles updates, 
                # OR just update the specific field to be safer/faster.
                # Let's use update directly for speed and safety.
                
                try:
                    update_res = supabase.table('hranalyzer_races').update({
                        'final_time': race_data['final_time'],
                        # Update these too if found, just in case
                        'fractional_times': ', '.join(race_data.get('fractional_times', [])) if race_data.get('fractional_times') else None
                    }).eq('id', race['id']).execute()
                    
                    if update_res.data:
                        success_count += 1
                        logger.info(f"Successfully updated {race_key}")
                    else:
                        fail_count += 1
                        logger.error(f"Failed to update DB for {race_key}")
                        
                except Exception as e:
                    logger.error(f"DB Error updating {race_key}: {e}")
                    fail_count += 1
                    
            else:
                logger.warning(f"Could not extract time for {race_key}")
                fail_count += 1

        logger.info(f"Backfill complete. Success: {success_count}, Failed: {fail_count}")

    except Exception as e:
        logger.error(f"Backfill script error: {e}")

if __name__ == "__main__":
    backfill_missing_times()
