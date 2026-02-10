
from supabase_client import get_supabase_client
import os
import sys

# Add libs to path if needed
sys.path.append('/home/xierra/Projects/horserace-analyzer/libs')

def check_all_prx():
    supabase = get_supabase_client()
    print("Fetching all PRX races from database...")
    res = supabase.table('hranalyzer_races')\
        .select('race_date, race_number, race_status, is_cancelled')\
        .eq('track_code', 'PRX')\
        .execute()
    
    if not res.data:
        print("No PRX races found.")
        return

    counts = {}
    details = {}
    for r in res.data:
        d = r['race_date']
        counts[d] = counts.get(d, 0) + 1
        if d not in details: details[d] = []
        details[d].append(r)
    
    print("\n--- PRX Race Counts by Date ---")
    for d in sorted(counts.keys()):
        print(f"{d}: {counts[d]} races")
        # If count is 11, show the race numbers
        if counts[d] == 11:
            nums = sorted([r['race_number'] for r in details[d]])
            print(f"  Race numbers: {nums}")

if __name__ == "__main__":
    check_all_prx()
