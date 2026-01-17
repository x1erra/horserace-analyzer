import os
import sys
import logging
from collections import defaultdict
from backend.supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_duplicates():
    supabase = get_supabase_client()
    logger.info("Starting duplicate cleanup (V3)...")

    # 1. Fetch ALL changes (can be large, but we need them all to group)
    # If too large, we might need pagination, but let's try direct fetch for now.
    logger.info("Fetching all changes...")
    response = supabase.table('hranalyzer_changes').select('*').execute()
    all_changes = response.data
    logger.info(f"Fetched {len(all_changes)} records.")

    # 2. Group by (race_id, entry_id, change_type)
    # Key: (race_id, entry_id, change_type) -> List of records
    groups = defaultdict(list)
    
    for ch in all_changes:
        # entry_id can be None
        key = (ch['race_id'], ch['entry_id'], ch['change_type'])
        groups[key].append(ch)

    deletions = []
    updates = []
    
    # 3. Analyze groups
    for key, records in groups.items():
        race_id, entry_id, change_type = key
        
        # SPECIAL CASE: "Race-wide" Scratches (entry_id is None, type='Scratch')
        # These are usually invalid ghosts unless specific logic says otherwise.
        # But wait, sometimes a generic scratch might exist? Unlikely for 'Scratch' type which implies a horse.
        if entry_id is None and change_type == 'Scratch':
            # Check if there are ANY specific scratches for this race?
            # Actually, user wants these gone. They are "nonsense".
            logger.info(f"Found Race-wide Scratch (Invalid): {len(records)} records. Marking for deletion.")
            for r in records:
                deletions.append(r['id'])
            continue

        # Normal Deduplication
        if len(records) > 1:
            # Sort by length of description (descending) to keep the "best" one, or merge.
            # We want to merge unique descriptions.
            
            unique_descs = set()
            ids_to_remove = []
            primary_id = None
            primary_record = None
            
            # Sort by created_at desc (keep newest? or oldest?)
            # Usually we want to keep the one with ID that might be referenced (none here).
            # Let's keep the one with the longest description as primary base.
            records.sort(key=lambda x: len(x.get('description') or ""), reverse=True)
            primary_record = records[0]
            primary_id = primary_record['id']
            
            merged_desc_parts = []
            if primary_record.get('description'):
                merged_desc_parts.append(primary_record['description'])
                unique_descs.add(primary_record['description'])
            
            for r in records[1:]:
                ids_to_remove.append(r['id'])
                d = r.get('description')
                if d and d not in unique_descs:
                    # Avoid merging subset strings e.g. "Scratched" into "Scratched - Vet"
                    # If d is substring of existing, skip
                    is_subset = False
                    for existing in unique_descs:
                        if d in existing: 
                            is_subset = True
                            break
                    if not is_subset:
                        merged_desc_parts.append(d)
                        unique_descs.add(d)

            final_desc = "; ".join(merged_desc_parts)
            
            # Queue Delete
            deletions.extend(ids_to_remove)
            
            # Queue Update if description changed
            if final_desc != primary_record['description']:
                updates.append({'id': primary_id, 'description': final_desc})
                
            logger.info(f"Group {key}: Found {len(records)} duplicates. Merging into {primary_id}. Deleting {len(ids_to_remove)}.")

    # 4. Execute Deletions
    if deletions:
        logger.info(f"Executing {len(deletions)} deletions...")
        # Batch delete
        batch_size = 100
        for i in range(0, len(deletions), batch_size):
            batch = deletions[i:i+batch_size]
            supabase.table('hranalyzer_changes').delete().in_('id', batch).execute()
        logger.info("Deletions complete.")
    else:
        logger.info("No deletions needed.")

    # 5. Execute Updates
    if updates:
        logger.info(f"Executing {len(updates)} description merges...")
        for up in updates:
            supabase.table('hranalyzer_changes').update({'description': up['description']}).eq('id', up['id']).execute()
        logger.info("Updates complete.")

    logger.info("Cleanup V3 Complete.")

if __name__ == "__main__":
    clean_duplicates()
