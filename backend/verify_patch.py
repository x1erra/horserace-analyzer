import sys
import os
from crawl_entries import crawl_entries
from supabase_client import get_supabase_client
from datetime import date


def verify_fix():
    print("Running crawl for ALL tracks to fix stale data...")
    # Force crawl for today for ALL tracks
    crawl_entries()
    
    print("\nChecking DB for resolved race types across ALL tracks...")
    supabase = get_supabase_client()
    today = date.today().isoformat()
    
    # Check race types for today's races
    res = supabase.table('hranalyzer_races')\
        .select('track_code, race_number, race_type, distance, surface')\
        .eq('race_date', today)\
        .order('track_code, race_number')\
        .execute()
        
    if not res.data:
        print("No races found for today.")
        return

    print(f"Found {len(res.data)} total races.")
    
    # Validation
    unknowns = [r for r in res.data if r['race_type'] == 'Unknown']
    if len(unknowns) == 0:
        print("\nSUCCESS: No 'Unknown' race types found across any tracks!")
    else:
        print(f"\nWARNING: {len(unknowns)} races still have 'Unknown' race type.")
        for u in unknowns:
            print(f"UNKNOWN: {u['track_code']} Race {u['race_number']}")

if __name__ == "__main__":
    verify_fix()

