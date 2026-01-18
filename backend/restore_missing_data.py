
import os
import sys
import logging
import re
from datetime import date, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client
from crawl_equibase import normalize_name, normalize_pgm

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restore_data")

def restore_data(days_back=30):
    supabase = get_supabase_client()
    
    start_date = date.today() - timedelta(days=days_back)
    logger.info(f"Restoring missing data since {start_date}")
    
    # 1. Restore Winner Program Numbers in Races
    logger.info("\n--- Restoring Winner Program Numbers ---")
    races = supabase.table('hranalyzer_races')\
        .select('id, race_key, race_date, winner_program_number')\
        .gte('race_date', start_date.isoformat())\
        .eq('race_status', 'completed')\
        .execute()
        
    if not races.data:
        logger.info("No completed races found.")
    else:
        logger.info(f"Checking {len(races.data)} races...")
        updates = 0
        for race in races.data:
            if race.get('winner_program_number'): 
                continue # Already has it
                
            race_id = race['id']
            # Find winner entry
            entries = supabase.table('hranalyzer_race_entries')\
                .select('program_number')\
                .eq('race_id', race_id)\
                .eq('finish_position', 1)\
                .limit(1)\
                .execute()
                
            if entries.data:
                win_pgm = entries.data[0]['program_number']
                if win_pgm:
                    supabase.table('hranalyzer_races')\
                        .update({'winner_program_number': win_pgm})\
                        .eq('id', race_id)\
                        .execute()
                    updates += 1
                    logger.info(f"Updated {race['race_key']}: Winner PGM = {win_pgm}")
        logger.info(f"Updated {updates} races with winner PGM.")

    # 2. Restore Claims Program Numbers
    logger.info("\n--- Restoring Claims Program Numbers ---")
    # Fetch all claims (not just nulls, just in case we want to fix specific ones)
    # Actually just fetch NULL ones to be safe and fast? 
    # Or fetch ALL to verify?
    # Let's fetch NULL ones first.
    claims = supabase.table('hranalyzer_claims')\
        .select('id, race_id, horse_name, program_number')\
        .is_('program_number', 'null')\
        .execute()
        
    if not claims.data:
        logger.info("No claims with missing Program Number found.")
    else:
        logger.info(f"Found {len(claims.data)} claims missing PGM. Attempting match...")
        fixed = 0
        for claim in claims.data:
            race_id = claim['race_id']
            # Need entries for this race
            entries = supabase.table('hranalyzer_race_entries')\
                .select('program_number, hranalyzer_horses(horse_name)')\
                .eq('race_id', race_id)\
                .execute()
                
            if not entries.data:
                continue
                
            found_pgm = None
            target_norm = normalize_name(claim['horse_name'])
            
            # Robust matching
            for e in entries.data:
                h_name = e.get('hranalyzer_horses', {}).get('horse_name', '')
                if normalize_name(h_name) == target_norm:
                    found_pgm = e.get('program_number')
                    break
            
            if found_pgm:
                supabase.table('hranalyzer_claims')\
                    .update({'program_number': found_pgm})\
                    .eq('id', claim['id'])\
                    .execute()
                fixed += 1
                logger.info(f"Fixed Claim {claim['horse_name']}: PGM {found_pgm}")
            else:
                logger.warning(f"Could not match claim '{claim['horse_name']}' in race {race_id}")
                
        logger.info(f"Fixed {fixed} claims.")

if __name__ == "__main__":
    restore_data()
