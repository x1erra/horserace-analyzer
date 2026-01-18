
import logging
from datetime import date
import sys
import os

# Add backend dir to path so we can import modules directly
sys.path.append(os.path.dirname(__file__))

# Import directly
from crawl_scratches import reset_scratches_for_date, process_rss_for_track, get_supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_hou_race():
    today = date.today()
    track_code = 'HOU'
    
    logger.info(f"Manual Fix: Resetting scratches/changes for {track_code} on {today}")
    
    # 1. Reset Scratches & Changes logic (local data)
    reset_scratches_for_date(track_code, today)
    
    # 2. Reset Race Status
    supabase = get_supabase_client()
    try:
        race_date_str = today.strftime('%Y-%m-%d')
        
        # Taking a safer approach: Select IDs first
        races = supabase.table('hranalyzer_races')\
            .select('id, race_status')\
            .eq('track_code', track_code)\
            .eq('race_date', race_date_str)\
            .eq('race_status', 'cancelled')\
            .execute()
            
        if races.data:
            ids = [r['id'] for r in races.data]
            logger.info(f"Found {len(ids)} cancelled races to re-open: {ids}")
            
            supabase.table('hranalyzer_races')\
                .update({'race_status': 'open'})\
                .in_('id', ids)\
                .execute()
            logger.info("Race statuses reset to 'open'.")
        else:
            logger.info("No races found marked as 'cancelled'.")

    except Exception as e:
        logger.error(f"Failed to reset race status: {e}")
        return

    # 3. Re-Crawl to get valid changes
    logger.info("Re-crawling RSS to populate valid changes...")
    count = process_rss_for_track(track_code)
    logger.info(f"Re-crawl complete. Processed {count} changes.")

if __name__ == "__main__":
    fix_hou_race()
