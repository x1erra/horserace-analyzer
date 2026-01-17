
import logging
from supabase_client import get_supabase_client
from supabase_client import get_supabase_client
# parse_cancellations_page removed, now using RSS
# from crawl_scratches import parse_cancellations_page, process_cancellations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_duplicates():
    supabase = get_supabase_client()
    logger.info("Starting cleanup...")
    
    # 1. DELETE INVALID RACE-WIDE SCRATCHES
    # These are changes with entry_id is null BUT type implies a horse
    invalid_types = ['Scratch', 'Jockey Change', 'Weight Change', 'Equipment Change']
    
    # We have to fetch and filter because delete with OR logic is tricky in one go
    # Actually, we can just iterate.
    
    logger.info("Scanning for invalid Race-wide entries...")
    res = supabase.table('hranalyzer_changes')\
        .select('*')\
        .is_('entry_id', 'null')\
        .in_('change_type', invalid_types)\
        .execute()
        
    deleted_count = 0
    for r in res.data:
        # Verify it's not actually a race-wide cancellation masquerading as scratch
        desc = r['description'].lower()
        if 'cancel' in desc:
            continue 
            
        logger.info(f"Deleting invalid race-wide entry: {r['id']} - {r['change_type']} - {r['description']}")
        supabase.table('hranalyzer_changes').delete().eq('id', r['id']).execute()
        deleted_count += 1
        
    logger.info(f"Deleted {deleted_count} invalid race-wide records.")
    
    # 2. DEDUPLICATE ENTRIES
    # Find groups of (race_id, entry_id, change_type) with count > 1
    # Since we can't do aggregation easily via client, we fetch all scratches for today/active races.
    # To cover everything, we might need to scan all. Or just active races.
    # Let's clean everything. FETCH ALL CHANGES
    
    logger.info("Fetching all changes for deduplication (this might take a moment)...")
    all_changes = []
    page = 0
    limit = 1000
    while True:
        r = supabase.table('hranalyzer_changes').select('*').range(page*limit, (page+1)*limit - 1).execute()
        if not r.data: break
        all_changes.extend(r.data)
        page += 1
        
    # Group keys
    groups = {}
    for c in all_changes:
        key = (c['race_id'], c['entry_id'], c['change_type']) # entry_id can be None
        if key not in groups: groups[key] = []
        groups[key].append(c)
        
    duplicates_removed = 0
    
    for key, records in groups.items():
        if len(records) > 1:
            # Sort/Filter
            # Logic: Prefer specific over "Reason Unavailable"
            
            # 1. Separate Specific vs Unavailable
            unavailable = [x for x in records if "Reason Unavailable" in (x['description'] or "")]
            specific = [x for x in records if "Reason Unavailable" not in (x['description'] or "")]
            
            to_keep = None
            
            if specific:
                # Keep the longest specific one? Or just the first one?
                # Merge checks?
                # If we have multiple specific ones, maybe merge them.
                # Example: "Vet" and "Injured"
                
                # Sort by length descending to keep most info
                specific.sort(key=lambda x: len(x['description'] or ""), reverse=True)
                to_keep = specific[0]
                
                # Delete all others
                to_delete = specific[1:] + unavailable
            else:
                # All are unavailable. Keep one.
                to_keep = unavailable[0]
                to_delete = unavailable[1:]
            
            if to_delete:
                ids = [x['id'] for x in to_delete]
                logger.info(f"Deduplicating {key}: Keeping {to_keep['id']} ({to_keep['description']}), deleting {len(ids)} others.")
                supabase.table('hranalyzer_changes').delete().in_('id', ids).execute()
                duplicates_removed += len(ids)
                
    logger.info(f"Deduplication complete. Removed {duplicates_removed} records.")

from crawl_scratches import process_rss_for_track

def force_rss_scan():
    # Force run the RSS logic for AQU (and others?)
    logger.info("Forcing RSS scan for AQU to catch cancellations...")
    process_rss_for_track('AQU')
    # Maybe fetch others? But AQU is the main issue.
    # The normal crawler loop will catch others.

if __name__ == "__main__":
    cleanup_duplicates()
    force_rss_scan()
