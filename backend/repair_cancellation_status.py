
import os
import sys
from supabase_client import get_supabase_client

def repair_cancelled_races():
    supabase = get_supabase_client()
    print("Repairing races incorrectly marked as cancelled...")

    # 1. basic fetch of all cancelled races
    response = supabase.table('hranalyzer_races')\
        .select('id, race_key, race_status, track_code, race_number')\
        .eq('race_status', 'cancelled')\
        .execute()

    cancelled_races = response.data
    print(f"Found {len(cancelled_races)} cancelled races to inspect.")

    repaired_count = 0
    
    for race in cancelled_races:
        # Check if it has results
        entries_res = supabase.table('hranalyzer_race_entries')\
            .select('finish_position')\
            .eq('race_id', race['id'])\
            .in_('finish_position', [1, 2, 3])\
            .execute()

        has_results = len(entries_res.data) > 0
        
        if has_results:
            print(f" -> FIXED: {race['race_key']} has results! Setting status to 'completed'.")
            supabase.table('hranalyzer_races')\
                .update({
                    'race_status': 'completed',
                    'is_cancelled': True, # Keep flag true as the event happened
                    'cancellation_reason': 'Cancellation detected but race has results (likely wagering cancellation)'
                })\
                .eq('id', race['id'])\
                .execute()
            repaired_count += 1
        else:
            # If no results, check if it was marked 'is_cancelled' properly
            # We can update the flag just in case
            supabase.table('hranalyzer_races')\
                .update({'is_cancelled': True})\
                .eq('id', race['id'])\
                .execute()
            # print(f" -> OK: {race['race_key']} is truly cancelled (no results).")

    print(f"\nRepaired {repaired_count} races.")

if __name__ == "__main__":
    repair_cancelled_races()
