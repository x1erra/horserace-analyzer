
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def check_winners():
    supabase = get_supabase_client()
    
    res = supabase.table('hranalyzer_races')\
        .select('race_key, winner_program_number')\
        .order('race_date', desc=True)\
        .limit(20)\
        .execute()
        
    if res.data:
        print("Winner Program Numbers for recent races:")
        for r in res.data:
            print(f"  - {r['race_key']}: {r['winner_program_number']}")
    else:
        print("No races found.")

if __name__ == "__main__":
    check_winners()
