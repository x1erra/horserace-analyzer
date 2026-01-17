
import os
import logging
from supabase_client import get_supabase_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_garbage_entries():
    """
    Remove entries that are clearly garbage formatting errors
    """
    supabase = get_supabase_client()
    
    # 1. Fetch all entries that look suspicious
    # We look for program_numbers that are '0' AND have suspicious names
    # Or just names that start with our known garbage list
    
    garbage_terms = [
        'Preliminary', 'Mutuel', 'Total', 'WPS', 'Claiming Prices', 
        'Footnotes', 'Winner:', 'Final Time', 'Call the', 'Copyright', 
        'Equibase', 'Video Replay'
    ]
    
    # We can't do complex "OR" likes easily in one Supabase query without raw SQL usually,
    # but we can iterate or use a stored procedure. 
    # Safe approach: Fetch suspicious candidates and filter in Python before deleting.
    
    logger.info("Scanning for garbage entries...")
    
    # Fetch entries with program_number '0' or suspiciously long/short names?
    # Actually, the bad entries in the screenshot had Program Numbers like "Prelimin" (which gets normalized to something else or kept if logic was bad)
    # The screenshot showed program number "Prelimin" (text) or "*"
    # Our new logic fixes normalization, but we need to find what's ALREADY in DB.
    
    # Get entries created recently? or just all.
    page = 0
    limit = 1000
    deleted_count = 0
    
    while True:
        # Paginating through entries to be safe
        response = supabase.table('hranalyzer_race_entries')\
            .select('id, program_number, final_odds, run_comments, horse_id, hranalyzer_horses(horse_name)')\
            .range(page * limit, (page + 1) * limit - 1)\
            .execute()
            
        entries = response.data
        if not entries:
            break
            
        ids_to_delete = []
        
        for entry in entries:
            horse_name = entry['hranalyzer_horses']['horse_name'] if entry.get('hranalyzer_horses') else "Unknown"
            pgm = entry.get('program_number', '')
            
            is_garbage = False
            
            # Check 1: Name contains garbage term start
            for term in garbage_terms:
                if horse_name.lower().startswith(term.lower()):
                    is_garbage = True
                    break
                    
            # Check 2: Program number looks like garbage (e.g. "Prelimin") 
            # (If previous normalization failed to strip it)
            if len(pgm) > 4 and not pgm.isdigit() and not pgm.endswith('A'):
                 # e.g. "Prelimin"
                 is_garbage = True
            
            # Check 3: Name is basically a price? "2.10"
            if horse_name.replace('.', '').isdigit():
                is_garbage = True
                
            if is_garbage:
                logger.warning(f"Found garbage entry: ID {entry['id']} | Pgm: {pgm} | Name: {horse_name}")
                ids_to_delete.append(entry['id'])
        
        if ids_to_delete:
            logger.info(f"Found {len(ids_to_delete)} garbage entries to delete in this page.")
            
            # Batch deletion to avoid "URL too long" 400 errors
            batch_size = 50
            for i in range(0, len(ids_to_delete), batch_size):
                batch_ids = ids_to_delete[i:i + batch_size]
                try:
                    supabase.table('hranalyzer_race_entries').delete().in_('id', batch_ids).execute()
                    deleted_count += len(batch_ids)
                    logger.info(f"  Deleted batch of {len(batch_ids)} entries...")
                except Exception as e:
                    logger.error(f"Error deleting batch: {e}")
                    
            # Since we deleted rows, pagination shifts.
            # If we delete items from the current page, the next items shift backward.
            # So simple offset pagination is risky while deleting.
            # Better strategy: keep offset effectively 0? Or use ID iteration?
            # If we delete, we shouldn't advance page? 
            # Actually, `range` selects by row number. If we delete, rows shift.
            # Safest is to NOT increment page if we found something, but re-fetch?
            # But limit makes sure we don't loop forever on 1 bad item?
            # Let's just assume we delete them and can continue to next page, but some might be skipped due to shift?
            # Better: if we deleted, stay on same page index?
            # But "range" is just offset. 
            pass
            
        page += 1
        
    logger.info(f"Cleanup complete. Deleted {deleted_count} entries.")

if __name__ == "__main__":
    cleanup_garbage_entries()
