
import os
import sys
from datetime import date
import logging

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_duplicate_changes():
    """
    Fetch all changes, group by Race/Horse/Type, identify duplicates, and delete inferior ones.
    """
    supabase = get_supabase_client()
    logger.info("Starting cleanup of duplicate changes...")

    # 1. Fetch all changes
    # We select essential fields + updated_at to break ties
    try:
        # Paging through in chunks just in case, though usually volume is manageable
        all_changes = []
        page = 0
        limit = 1000
        while True:
            res = supabase.table('hranalyzer_changes')\
                .select('''
                    id, race_id, entry_id, change_type, description, created_at,
                    entry:hranalyzer_race_entries(horse_id)
                ''')\
                .range(page*limit, (page+1)*limit - 1)\
                .execute()
                
            if not res.data:
                break
            
            all_changes.extend(res.data)
            page += 1
            if len(res.data) < limit:
                break
                
        logger.info(f"Fetched {len(all_changes)} records to analyze.")
        
    except Exception as e:
        logger.error(f"Error fetching changes: {e}")
        return

    # 2. Grouping by RACE + ENTITY (Horse)
    grouped = {}
    
    for c in all_changes:
        rid = c['race_id']
        eid = c['entry_id']
        
        # Resolve Entity Key
        if eid:
            key = f"{rid}|ENTRY|{eid}"
        else:
            # Fallback for race-wide or orphan
            # We need to be careful not to group different race-wide messages together blindly
            # But for "A Lister" (orphan?), we might have horse_name in description or separate field?
            # actually hranalyzer_changes doesn't store horse_name directly, it links to entry.
            # If entry_id is null, it's irrelevant for "A Lister" cleanup usually (unless our crawler failed to link).
            # The A Lister example in debug output likely HAS an entry_id, just different types.
            key = f"{rid}|ORPHAN|{c['change_type']}"

        if key not in grouped: grouped[key] = []
        grouped[key].append(c)
        
    # 3. Identify records to delete
    ids_to_delete = []
    
    for key, group in grouped.items():
        if len(group) <= 1:
            continue
            
        # Strategy:
        # A) Identify if we have a "Master" Scratch record
        # B) Identify redundant "Other" records
        
        has_scratch = False
        scratch_records = []
        other_records = []
        
        for r in group:
            ctype = (r.get('change_type') or "").strip()
            if ctype == 'Scratch':
                has_scratch = True
                scratch_records.append(r)
            else:
                other_records.append(r)
                
        # Rule 1: Clean up multiple "Scratch" records
        if len(scratch_records) > 1:
            # Keep best scratch
            def score_scratch(r):
                s = 0
                desc = (r.get('description') or "").lower()
                if "reason unavailable" in desc: s -= 10
                s += len(desc)
                return s
            
            scratch_records.sort(key=lambda x: (score_scratch(x), x.get('created_at') or ''), reverse=True)
            # Keep index 0, delete rest
            for bad in scratch_records[1:]:
                logger.info(f"Marking duplicate Scratch for deletion: {bad['id']} ({bad['description']})")
                ids_to_delete.append(bad['id'])
        
        # Rule 2: If we have a Scratch, remove "Other" records that are about Scratch Reasons
        if has_scratch or len(scratch_records) > 0: # has_scratch is true if len > 0
            for other in other_records:
                desc = (other.get('description') or "").lower()
                # Check for redness patterns
                if "scratch" in desc or "reason" in desc:
                    # It's likely a "Scratch Reason - ..." log
                    logger.info(f"Marking redundant Other for deletion: {other['id']} ({other['description']})")
                    ids_to_delete.append(other['id'])
                    
        # Rule 3: If NO Scratch, but multiple Others?
        # Maybe dedup them if identical? 
        # Leave for now to be safe.
            
    logger.info(f"Found {len(ids_to_delete)} duplicate records to delete.")
            
    logger.info(f"Found {len(ids_to_delete)} duplicate records to delete.")
    
    if not ids_to_delete:
        logger.info("No duplicates found to delete.")
        return

    # 4. Batch Delete
    # Supabase might limit batch size for 'in' filter
    batch_size = 100
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i:i+batch_size]
        try:
            supabase.table('hranalyzer_changes')\
                .delete()\
                .in_('id', batch)\
                .execute()
            logger.info(f"Deleted batch {i//batch_size + 1}")
        except Exception as e:
            logger.error(f"Error deleting batch: {e}")

    logger.info("Cleanup completed successfully.")

if __name__ == "__main__":
    cleanup_duplicate_changes()
