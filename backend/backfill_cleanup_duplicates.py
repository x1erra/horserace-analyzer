import logging
import re
import time
from typing import Dict, List
from supabase_client import get_supabase_client
from crawl_equibase import normalize_pgm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def backfill_fix_duplicates():
    """
    Scans the database for entries with non-normalized Program Numbers (e.g. '08', '01A').
    1. If a normalized version ('8') ALREADY exists in the same race -> MERGE.
       - Copy results from '8' (likely bad name/result) to '08' (likely good name/no result)
       - OR vice versa depending on which one looks "better" (has results).
       - Actually: entries from 'crawl_entries' (08) have GOOD NAMES (with spaces).
       - Entries from 'crawl_equibase' (8) have BAD NAMES (squeezed) but HAVE RESULTS.
       - So we want to:
         1. Take '08' (Good Name).
         2. Take '8' (Results).
         3. Update '08' with '8's results.
         4. Change '08' -> '8'.
         5. Delete old '8'.
    2. If NO collision -> Just update '08' -> '8'.
    """
    supabase = get_supabase_client()
    
    # Fetch all entries.
    # Optimized: iterate by race?
    # Or just fetch all entries with leading zeros?
    # regex filter: program_number like '0%'
    
    logger.info("Fetching potential duplicate candidates (PGM starts with '0')...")
    
    # Note: .like('program_number', '0%') might include '0'? 
    # normalize_pgm('0') -> '0' so that's fine.
    
    # Page through results
    limit = 1000
    offset = 0
    total_processed = 0
    total_merged = 0
    total_renamed = 0
    
    while True:
        logger.info(f"Fetching page offset {offset}...")
        response = supabase.table('hranalyzer_race_entries')\
            .select('id, race_id, program_number, finish_position, horse_id, scratched')\
            .like('program_number', '0%')\
            .order('id')\
            .range(offset, offset + limit - 1)\
            .execute()
            
        entries = response.data
        if not entries:
            break
            
        for entry in entries:
            raw_pgm = entry['program_number']
            norm_pgm = normalize_pgm(raw_pgm)
            
            # If already normalized (e.g. '0'), skip
            if raw_pgm == norm_pgm:
                continue
                
            race_id = entry['race_id']
            entry_id = entry['id']
            
            # Check for COLLISION: Does 'norm_pgm' exist in this race?
            collision_res = supabase.table('hranalyzer_race_entries')\
                .select('*')\
                .eq('race_id', race_id)\
                .eq('program_number', norm_pgm)\
                .execute()
                
            if collision_res.data:
                # COLLISION DETECTED!
                # entry is "08" (Candidate)
                # target is "8" (Existing Normalized)
                target = collision_res.data[0]
                
                logger.info(f"Collision found for Race {race_id}: '{raw_pgm}' vs '{norm_pgm}'")
                
                # Merge Strategy:
                # We want to keep the entry that has the BETTER HORSE NAME usually.
                # But we don't have horse names joined here.
                # Heuristic: '08' usually comes from Morning Line (Good Name).
                # '8' usually comes from Result (Bad Name).
                
                # 1. Update Candidate ('08') with results from Target ('8')
                update_payload = {}
                
                # Copy result fields if Candidate is missing them
                for field in ['finish_position', 'win_payout', 'place_payout', 'show_payout', 'final_odds', 'run_comments', 'speed_figure']:
                    if target.get(field) is not None and entry.get(field) is None:
                        update_payload[field] = target[field]
                        
                # 2. Delete Target ('8') 
                # (We must delete it BEFORE renaming Candidate to avoid unique constraint violation)
                logger.info(f"  -> Deleting duplicate target {target['id']} (PGM {norm_pgm})")
                supabase.table('hranalyzer_race_entries').delete().eq('id', target['id']).execute()
                
                # 3. Rename Candidate ('08') -> '8' AND apply updates
                update_payload['program_number'] = norm_pgm
                # Also unset scratched if target had a result?
                if target.get('finish_position'):
                    update_payload['scratched'] = False
                    
                logger.info(f"  -> Updating/Renaming candidate {entry_id} ({raw_pgm} -> {norm_pgm})")
                supabase.table('hranalyzer_race_entries').update(update_payload).eq('id', entry_id).execute()
                
                total_merged += 1
                
            else:
                # NO COLLISION
                # Just rename
                # logger.info(f"Renaming {raw_pgm} -> {norm_pgm}")
                supabase.table('hranalyzer_race_entries')\
                    .update({'program_number': norm_pgm})\
                    .eq('id', entry_id)\
                    .execute()
                total_renamed += 1
                
        total_processed += len(entries)
        offset += limit
        
        # Safety break
        if len(entries) < limit:
            break
            
    logger.info("="*50)
    logger.info(f"PGM Backfill Complete.")
    logger.info(f"Total Processed: {total_processed}")
    logger.info(f"Merged Duplicates: {total_merged}")
    logger.info(f"Renamed Only: {total_renamed}")
    logger.info("="*50)
    
    # Run Name-Based Dedup
    backfill_dedup_names(supabase)

def backfill_dedup_names(supabase):
    """
    Second Pass: Deduplicate entries within the same race that have matching NORMALIZED names.
    e.g. "Stayed in for Half" (Entry) vs "StayedinforHalf" (Result).
    This handles cases where PGMs might be different or identical but split rows exist.
    """
    logger.info("Starting Name-Based Deduplication...")
    
    from crawl_equibase import normalize_name
    
    # We iterate by race to be efficient? No, fetching all races is expensive.
    # Let's fetch ranges of races from 'hranalyzer_race_entries' ordered by race_id.
    
    # To do this efficiently without fetching 100k rows:
    # Maybe filtering for races with > 0 entries?
    
    # Let's iterate distinct race_ids?
    # Or simplified: Fetch all entries, processing locally (Python dict) in chunks.
    # We need to process PER RACE.
    
    # Strategy: Fetch ordered by race_id. Group by race_id in loop.
    
    offset = 0
    limit = 2000
    current_race_id = None
    race_entries = []
    
    total_name_merges = 0
    
    while True:
        logger.info(f"Fetching entries for name dedup (offset {offset})...")
        # We need horse name included
        res = supabase.table('hranalyzer_race_entries')\
            .select('id, race_id, program_number, finish_position, horse_id, scratched, hranalyzer_horses(horse_name)')\
            .order('race_id')\
            .range(offset, offset + limit - 1)\
            .execute()
            
        rows = res.data
        if not rows:
            break
            
        for row in rows:
            rid = row['race_id']
            
            if rid != current_race_id:
                # Process previous race buffer
                if current_race_id and race_entries:
                    total_name_merges += process_race_dedup(supabase, current_race_id, race_entries)
                
                # Reset
                current_race_id = rid
                race_entries = []
            
            race_entries.append(row)
            
        offset += limit
        
    # Process last buffer
    if current_race_id and race_entries:
        total_name_merges += process_race_dedup(supabase, current_race_id, race_entries)
        
    logger.info(f"Name-Based Dedup Complete. Merged {total_name_merges} sets.")


def process_race_dedup(supabase, race_id, entries):
    """
    Check for fuzzy duplicates in a list of entries for a single race.
    Returns number of merges performed.
    """
    from crawl_equibase import normalize_name
    
    merges = 0
    
    # Map: norm_name -> list of entries
    name_map = {}
    
    for e in entries:
        horse = e.get('hranalyzer_horses')
        if not horse: continue
        
        name = horse.get('horse_name', '')
        norm = normalize_name(name)
        
        if norm not in name_map:
            name_map[norm] = []
        name_map[norm].append(e)
        
    # Check for collisions
    for norm, group in name_map.items():
        if len(group) > 1:
            # DUPLICATE DETECTED
            # e.g. "StayedinforHalf" and "Stayed in for Half"
            
            # 1. Identify "Best" Entry (Keeper)
            # Criteria: 
            # - Has Spaces in name (Preferred)
            # - Has Results (Secondary)
            
            # Sort group:
            # Priority 1: Name length (proxy for spaces? No, exact length. Spaces count.)
            # Priority 2: Has finish_position?
            
            # Helper to score entry
            def score_entry(x):
                h_name = x['hranalyzer_horses']['horse_name']
                has_result = 1 if x.get('finish_position') else 0
                space_count = h_name.count(' ')
                return (space_count, has_result)
            
            # Sort descending (Higher score = Better)
            group.sort(key=score_entry, reverse=True)
            
            # Winner is index 0
            winner = group[0]
            winner_name = winner['hranalyzer_horses']['horse_name']
            
            logger.info(f"Deduping race {race_id}: Keeping '{winner_name}' (ID {winner['id']})")
            
            # Merge others into Winner
            for loser in group[1:]:
                loser_name = loser['hranalyzer_horses']['horse_name']
                logger.info(f"  -> Merging/Deleting duplicate '{loser_name}' (ID {loser['id']})")
                
                # Copy results if Winner lacks them
                update_payload = {}
                dirty = False
                
                for field in ['finish_position', 'win_payout', 'place_payout', 'show_payout', 'final_odds', 'run_comments', 'speed_figure']:
                    if winner.get(field) is None and loser.get(field) is not None:
                        update_payload[field] = loser[field]
                        dirty = True
                
                # Also normalize PGM if needed?
                # If winner PGM is '08' and loser is '8', maybe update to '8'?
                # PGM Normalization handled by first pass, but let's be safe.
                # normalize_pgm is available.
                
                if dirty:
                    supabase.table('hranalyzer_race_entries').update(update_payload).eq('id', winner['id']).execute()
                    
                # Delete Loser
                try:
                    supabase.table('hranalyzer_race_entries').delete().eq('id', loser['id']).execute()
                    merges += 1
                except Exception as e:
                    logger.error(f"Error deleting duplicate {loser['id']}: {e}")

    return merges

if __name__ == "__main__":
    backfill_fix_duplicates()

