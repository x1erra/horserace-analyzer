
import logging
import time
from datetime import datetime, date
from supabase_client import get_supabase_client
from crawl_equibase import build_equibase_url, extract_race_from_pdf, insert_race_to_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('fix_missing_winners')

def fix_missing_winners(target_date=None):
    supabase = get_supabase_client()
    
    # Defaults to today if not provided, but we usually want to check past races
    if not target_date:
        target_date = date.today().strftime('%Y-%m-%d')
        
    logger.info(f"Checking for races with missing winners on/before {target_date}...")

    # 1. Fetch all 'completed' races
    # limimiting to recent 1000 to avoid overly long query on full history if DB is huge
    # or just filter by date range if needed. Let's look at last 7 days for now or passed date.
    
    query = supabase.table('hranalyzer_races')\
        .select('id, race_key, track_code, race_date, race_number, race_status')\
        .eq('race_status', 'completed')\
        .lte('race_date', target_date)\
        .order('race_date', desc=True)\
        .limit(200)\
        .execute()
        
    races = query.data
    logger.info(f"Found {len(races)} completed races to check.")
    
    fixed_count = 0
    
    for race in races:
        race_id = race['id']
        race_key = race['race_key']
        track_code = race['track_code']
        race_date_str = race['race_date']
        race_number = race['race_number']
        
        # Check if winner exists
        # We look for ANY entry with finish_position = 1
        curr_entries = supabase.table('hranalyzer_race_entries')\
            .select('id')\
            .eq('race_id', race_id)\
            .eq('finish_position', 1)\
            .execute()
            
        if not curr_entries.data:
            logger.warning(f"MISSING WINNER: {race_key} ({race_date_str}). Repairing...")
            
            # Convert date str to date obj
            r_date = datetime.strptime(race_date_str, '%Y-%m-%d').date()
            
            # Re-crawl
            pdf_url = build_equibase_url(track_code, r_date, race_number)
            race_data = extract_race_from_pdf(pdf_url, max_retries=2)
            
            if race_data and race_data.get('horses'):
                # Insert (Update)
                success = insert_race_to_db(supabase, track_code, r_date, race_data, race_number)
                if success:
                    logger.info(f"✓ REPAIRED {race_key}")
                    fixed_count += 1
                else:
                    logger.error(f"✗ FAILED to repair {race_key} (DB Insert failed)")
            else:
                logger.error(f"✗ FAILED to repair {race_key} (PDF extraction failed)")
                
            time.sleep(1.5) 
            
    logger.info(f"Repair complete. Fixed {fixed_count} races.")

if __name__ == "__main__":
    import sys
    # Optional date arg
    d = None
    if len(sys.argv) > 1:
        d = sys.argv[1]
    fix_missing_winners(d)
