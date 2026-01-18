"""
Backfill script to populate program_number for existing claims
"""
import os
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client
from crawl_equibase import normalize_name

def backfill_claim_program_numbers():
    """Backfill program_number for existing claims"""
    supabase = get_supabase_client()
    
    # Get all claims missing program_number
    claims = supabase.table('hranalyzer_claims')\
        .select('id, race_id, horse_name, program_number')\
        .is_('program_number', 'null')\
        .execute()
    
    print(f"Found {len(claims.data)} claims missing program_number")
    
    updated = 0
    failed = 0
    
    for claim in claims.data:
        race_id = claim['race_id']
        horse_name = claim['horse_name']
        norm_claim = normalize_name(horse_name)
        
        # Lookup program_number from race entries
        entries = supabase.table('hranalyzer_race_entries')\
            .select('program_number, hranalyzer_horses(horse_name)')\
            .eq('race_id', race_id)\
            .execute()
        
        found_pgm = None
        
        if entries.data:
            # 1. Exact Match on Normalized Name
            for entry in entries.data:
                db_horse = entry.get('hranalyzer_horses') or {}
                db_name = db_horse.get('horse_name', '')
                if normalize_name(db_name) == norm_claim:
                    found_pgm = entry.get('program_number')
                    break
            
            # 2. Fuzzy Match (Contains) if no exact match
            if not found_pgm and len(norm_claim) > 4:
                for entry in entries.data:
                    db_horse = entry.get('hranalyzer_horses') or {}
                    db_name = db_horse.get('horse_name', '')
                    norm_db = normalize_name(db_name)
                    
                    # Check containment (one way or the other)
                    if (norm_claim in norm_db) or (norm_db in norm_claim):
                         # Ensure we don't match short strings inappropriately
                         found_pgm = entry.get('program_number')
                         print(f"  > Fuzzy matched '{horse_name}' to '{db_name}'")
                         break
                         
        if found_pgm:
            # Update the claim
            try:
                supabase.table('hranalyzer_claims')\
                    .update({'program_number': found_pgm})\
                    .eq('id', claim['id'])\
                    .execute()
                print(f"Updated claim for {horse_name} with program #{found_pgm}")
                updated += 1
            except Exception as e:
                print(f"Error updating claim {claim['id']}: {e}")
        else:
            print(f"FAILED to match: {horse_name} (Race {race_id})")
            failed += 1
    
    print(f"\nBackfill complete! Updated: {updated}, Failed: {failed}")

if __name__ == "__main__":
    backfill_claim_program_numbers()
