import logging
from supabase_client import get_supabase_client

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def final_aggressive_merge():
    supabase = get_supabase_client()
    logger.info("Starting final aggressive merge...")
    
    res = supabase.table('hranalyzer_changes').select('*').execute()
    all_changes = res.data
    logger.info(f"Processing {len(all_changes)} records...")
    
    merge_map = {}
    for c in all_changes:
        # Key on race, entry, and type
        key = (c['race_id'], c['entry_id'], c['change_type'])
        if key not in merge_map:
            merge_map[key] = []
        merge_map[key].append(c)
        
    merged_count = 0
    for key, group in merge_map.items():
        if len(group) > 1:
            # Sort by description length (longest first)
            group.sort(key=lambda x: len(x['description'] or ""), reverse=True)
            main = group[0]
            others = group[1:]
            
            # Merge descriptions uniquely
            descs = [main['description']]
            for o in others:
                d = o['description']
                if d and d not in descs:
                    # Check substring
                    is_sub = False
                    for existing in descs:
                        if d in existing: is_sub = True; break
                    if not is_sub:
                        descs.append(d)
            
            new_desc = "; ".join(descs)
            if len(new_desc) > 500: new_desc = new_desc[:497] + "..."
            
            # Update main
            supabase.table('hranalyzer_changes').update({'description': new_desc}).eq('id', main['id']).execute()
            
            # Delete others
            for o in others:
                supabase.table('hranalyzer_changes').delete().eq('id', o['id']).execute()
                merged_count += 1
                
    logger.info(f"Force-merged {merged_count} remaining duplicates.")

if __name__ == "__main__":
    final_aggressive_merge()
