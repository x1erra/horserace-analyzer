import logging
import time
from supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def debug_and_fix():
    supabase = get_supabase_client()
    
    # 1. DELETE ALL orphans where entry_id is NULL (except Race Cancelled and Surface Change)
    keep_types = ['Race Cancelled', 'Surface Change']
    logger.info("Cleaning up ALL orphans (entry_id is NULL) except Race Cancelled/Surface Change...")
    
    res = supabase.table('hranalyzer_changes')\
        .delete()\
        .is_('entry_id', 'null')\
        .not_.in_('change_type', keep_types)\
        .execute()
    
    logger.info(f"  -> Deleted {len(res.data) if res.data else 0} orphans.")

    # 2. MERGE DUPLICATES more aggressively
    # We'll merge based on (race_id, horse_name or entry_id, change_type)
    # Actually, let's fetch entries with horse names to be sure
    
    offset = 0
    limit = 1000
    all_changes = []
    
    while True:
        res = supabase.table('hranalyzer_changes')\
            .select('*, hranalyzer_race_entries(id, hranalyzer_horses(horse_name))')\
            .order('created_at')\
            .range(offset, offset + limit - 1)\
            .execute()
        if not res.data: break
        all_changes.extend(res.data)
        offset += limit
        if len(res.data) < limit: break

    merge_map = {}
    for c in all_changes:
        entry = c.get('hranalyzer_race_entries')
        horse_name = "UNKNOWN"
        if entry and entry.get('hranalyzer_horses'):
            horse_name = entry['hranalyzer_horses']['horse_name']
        
        # Key: (race_id, horse_name, change_type)
        key = (c['race_id'], horse_name, c['change_type'])
        if key not in merge_map:
            merge_map[key] = []
        merge_map[key].append(c)

    total_merged = 0
    for key, records in merge_map.items():
        if len(records) > 1:
            main = records[0]
            to_delete = records[1:]
            
            descs = []
            for r in records:
                d = (r['description'] or "").strip()
                if d and d not in descs:
                    # Check if already a substring
                    is_sub = False
                    for existing in descs:
                        if d in existing: 
                            is_sub = True
                            break
                        if existing in d:
                            descs.remove(existing)
                            break
                    if not is_sub:
                        descs.append(d)
            
            new_desc = "; ".join(descs)
            if len(new_desc) > 500: new_desc = new_desc[:497] + "..."
            
            if new_desc != main['description']:
                supabase.table('hranalyzer_changes')\
                    .update({'description': new_desc})\
                    .eq('id', main['id'])\
                    .execute()
            
            for r in to_delete:
                supabase.table('hranalyzer_changes').delete().eq('id', r['id']).execute()
                total_merged += 1
                
    logger.info(f"Merged {total_merged} duplicates.")

if __name__ == "__main__":
    debug_and_fix()
