import sys
import os
from crawl_entries import crawl_entries
from supabase_client import get_supabase_client
from datetime import date

def verify_fix():
    print("Running crawl for Fair Grounds (FG)...")
    # Force crawl for today
    crawl_entries(tracks=['FG'])
    
    print("\nChecking DB for resolved race types...")
    supabase = get_supabase_client()
    today = date.today().isoformat()
    
    # Check race types for today's FG races
    res = supabase.table('hranalyzer_races')\
        .select('race_number, race_type, distance, surface')\
        .eq('track_code', 'FG')\
        .eq('race_date', today)\
        .order('race_number')\
        .execute()
        
    if not res.data:
        print("No races found for FG today.")
        return

    print(f"Found {len(res.data)} races:")
    for race in res.data:
        print(f"Race {race['race_number']}: Type='{race['race_type']}' (Dist={race['distance']}, Surf={race['surface']})")
        
    # Validation
    unknowns = [r for r in res.data if r['race_type'] == 'Unknown']
    if len(unknowns) == 0:
        print("\nSUCCESS: No 'Unknown' race types found!")
    else:
        print(f"\nWARNING: {len(unknowns)} races still have 'Unknown' race type.")

if __name__ == "__main__":
    verify_fix()
