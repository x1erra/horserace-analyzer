
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def check_completed_winners():
    supabase = get_supabase_client()
    
    # Check races valid for backfill (e.g. Jan 17th)
    res = supabase.table('hranalyzer_races')\
        .select('race_key, race_date, winner_program_number')\
        .eq('race_status', 'completed')\
        .order('race_date', desc=True)\
        .limit(20)\
        .execute()
        
    if res.data:
        print("Winner Program Numbers for COMPLETED races:")
        for r in res.data:
            print(f"  - {r['race_key']} ({r['race_date']}): {r['winner_program_number']}")
    else:
        print("No completed races found.")

if __name__ == "__main__":
    check_completed_winners()
