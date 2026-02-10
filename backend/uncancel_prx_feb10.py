
from supabase_client import get_supabase_client
import os
import sys

# Add libs to path
sys.path.append('/home/xierra/Projects/horserace-analyzer/libs')

def uncancel_prx_feb10():
    supabase = get_supabase_client()
    
    print("Un-cancelling Parx Racing races for 2026-02-10...")
    
    # Reset status to 'upcoming' and is_cancelled to False
    res = supabase.table('hranalyzer_races')\
        .update({
            'race_status': 'upcoming',
            'is_cancelled': False,
            'cancellation_reason': None
        })\
        .eq('track_code', 'PRX')\
        .eq('race_date', '2026-02-10')\
        .execute()
    
    if res.data:
        print(f"Successfully updated {len(res.data)} races.")
        for r in res.data:
            print(f"Race {r['race_number']} reset to upcoming.")
    else:
        print("No races found to update.")

if __name__ == "__main__":
    uncancel_prx_feb10()
