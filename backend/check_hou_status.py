
from supabase_client import get_supabase_client
import sys

def check_hou_race():
    supabase = get_supabase_client()
    
    print("\n--- Checking HOU Race 2 for Today ---")
    races = supabase.table('hranalyzer_races')\
        .select('*')\
        .eq('track_code', 'HOU')\
        .eq('race_number', 2)\
        .order('race_date', desc=True)\
        .limit(1)\
        .execute()
        
    if not races.data:
        print("HOU Race 2 not found")
        return

    r = races.data[0]
    print(f"Date: {r['race_date']}")
    print(f"Race Status: {r['race_status']}")
    print(f"Race ID: {r['id']}")
    
    # Check if there are any 'Race Cancelled' changes for this race
    changes = supabase.table('hranalyzer_changes')\
        .select('*')\
        .eq('race_id', r['id'])\
        .execute()
        
    for c in changes.data:
        print(f"Change: {c['change_type']} - {c['description']}")

if __name__ == "__main__":
    check_hou_race()
