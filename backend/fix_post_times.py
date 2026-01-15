
import os
import re
import logging
from supabase_client import get_supabase_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FixPostTimes")

def fix_post_times():
    supabase = get_supabase_client()
    
    logger.info("Fetching races with 'Post Time' in post_time field...")
    
    # We can't use 'ilike' easily with python client depending on version, 
    # but we can fetch all upcoming races for today/future or just all races.
    # Given the scale, let's fetch all races from recent days or just all races with 'Post' in post_time column if possible?
    
    # Or just fetch all races where race_status is 'upcoming' or 'completed' and process in batches.
    # Let's fetch ALL races. It's not that big yet.
    
    try:
        response = supabase.table('hranalyzer_races').select('id, track_code, race_date, post_time').execute()
        
        count = 0
        fixed = 0
        
        for race in response.data:
            pt = race.get('post_time')
            if not pt:
                continue
                
            original_pt = pt
            
            # Check if it needs fixing
            if "Post" in pt or "Time" in pt or "ET" in pt or "AM" in pt or "PM" in pt:
                # 1. Remove "Post Time"
                clean_pt = pt.replace("Post Time", "").replace("Post time", "").replace(":", " ").replace("  ", " ").strip()
                # Wait, don't remove the colon in the time itself!
                clean_pt = pt.replace("Post Time", "").replace("Post time", "").strip()
                
                # 2. Remove "ET"
                clean_pt = clean_pt.replace("ET", "").strip()
                
                # 3. Ensure it's clean.. just double check
                clean_pt = clean_pt.replace(":", ":") # no-op
                
                # If changed
                if clean_pt != original_pt:
                    # Update DB
                    logger.info(f"Fixing Race {race['id']} ({race['track_code']} {race['race_date']}): '{original_pt}' -> '{clean_pt}'")
                    try:
                        supabase.table('hranalyzer_races').update({'post_time': clean_pt}).eq('id', race['id']).execute()
                        fixed += 1
                    except Exception as e:
                        logger.error(f"Failed to update race {race['id']}: {e}")
            
            count += 1
            
        logger.info(f"Scanned {count} races. Fixed {fixed} records.")
        
    except Exception as e:
        logger.error(f"Error scanning races: {e}")

if __name__ == "__main__":
    fix_post_times()
