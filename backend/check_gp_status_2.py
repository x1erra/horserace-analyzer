
from supabase_client import get_supabase_client
import sys

def check_gp_race():
    supabase = get_supabase_client()
    
    print("\n--- Checking GP Race 2 for 2026-01-18 ---")
    races = supabase.table('hranalyzer_races')\
        .select('*')\
        .eq('track_code', 'GP')\
        .eq('race_date', '2026-01-18')\
        .eq('race_number', 2)\
        .execute()
        
    if not races.data:
        print("GP Race 2 not found")
        return

    r = races.data[0]
    print(f"Race Status: {r['race_status']}")
    print(f"Race ID: {r['id']}")
    
    # Check entries
    entries = supabase.table('hranalyzer_race_entries')\
        .select('*')\
        .eq('race_id', r['id'])\
        .execute()
        
    print(f"Total Entries: {len(entries.data)}")
    has_results = False
    for e in entries.data:
        if e['finish_position']:
            print(f"Entry {e['program_number']} Finished: {e['finish_position']}")
            has_results = True
            
    if has_results:
        print("CONCLUSION: Race has results but status might be cancelled.")
    else:
        print("CONCLUSION: Race has NO results.")

if __name__ == "__main__":
    check_gp_race()
