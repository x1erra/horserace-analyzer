import logging
import time
from supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fix_bad_changes():
    """
    Cleans up the hranalyzer_changes table:
    1. Removes 'Race-wide' orphans for horse-specific changes.
    2. Deduplicates horse changes by merging descriptions.
    """
    supabase = get_supabase_client()
    
    # 1. REMOVE ORPHANS
    # Delete horse-specific changes where entry_id is NULL
    horse_specific_types = ['Scratch', 'Jockey Change', 'Weight Change', 'Equipment Change']
    
    logger.info(f"Removing orphan changes (types: {horse_specific_types})...")
    
    # We have to do this in batches or one by one if the lib doesn't support 'in' easily for delete
    for ctype in horse_specific_types:
        try:
            res = supabase.table('hranalyzer_changes')\
                .delete()\
                .eq('change_type', ctype)\
                .is_('entry_id', 'null')\
                .execute()
            count = len(res.data) if res.data else 0
            logger.info(f"  -> Deleted {count} orphans for type {ctype}")
        except Exception as e:
            logger.error(f"Error deleting orphans for {ctype}: {e}")

    # 2. DEDUPLICATE / MERGE
    logger.info("Scanning for duplicates to merge...")
    
    # Fetch all changes group by (race_id, entry_id, change_type)
    # Since we can't easily group in Supabase client, we'll fetch all and process in Python
    # This might be large, so we'll page it.
    
    limit = 1000
    offset = 0
    merge_map = {} # (race_id, entry_id, change_type) -> list of records
    
    while True:
        res = supabase.table('hranalyzer_changes')\
            .select('id, race_id, entry_id, change_type, description')\
            .order('created_at')\
            .range(offset, offset + limit - 1)\
            .execute()
            
        rows = res.data
        if not rows:
            break
            
        for row in rows:
            key = (row['race_id'], row['entry_id'], row['change_type'])
            if key not in merge_map:
                merge_map[key] = []
            merge_map[key].append(row)
            
        offset += limit
        if len(rows) < limit:
            break

    # Process merges
    total_merged = 0
    for key, records in merge_map.items():
        if len(records) > 1:
            # We have duplicates!
            # Keep the first one (oldest by created_at since we ordered by created_at)
            main_record = records[0]
            to_delete = records[1:]
            
            # Merge descriptions
            unique_descs = []
            for r in records:
                desc = (r['description'] or "").strip()
                if desc and desc not in unique_descs:
                    # Check if it's already a substring of another
                    already_partial = False
                    for existing in unique_descs:
                        if desc in existing:
                            already_partial = True
                            break
                        if existing in desc:
                            unique_descs.remove(existing)
                            break
                    if not already_partial:
                        unique_descs.append(desc)
            
            merged_desc = "; ".join(unique_descs)
            if len(merged_desc) > 500: merged_desc = merged_desc[:497] + "..."
            
            # Update main
            if merged_desc != main_record['description']:
                supabase.table('hranalyzer_changes')\
                    .update({'description': merged_desc})\
                    .eq('id', main_record['id'])\
                    .execute()
            
            # Delete others
            for r in to_delete:
                supabase.table('hranalyzer_changes').delete().eq('id', r['id']).execute()
                total_merged += 1

    logger.info(f"Merged {total_merged} duplicate records.")
    logger.info("Cleanup complete.")

if __name__ == "__main__":
    fix_bad_changes()
