
from supabase_client import get_supabase_client
from datetime import date
import sys

# Add libs to path
sys.path.append('/home/xierra/Projects/horserace-analyzer/libs')

def verify_past_races_query():
    supabase = get_supabase_client()
    today = date.today().isoformat()
    
    print(f"Querying for past races including cancelled on {today}...")
    
    # Replicate the query from backend.py
    query = supabase.table('hranalyzer_races')\
        .select('race_date, track_code, race_status')\
        .lte('race_date', today)\
        .in_('race_status', ['completed', 'past_drf_only', 'cancelled'])\
        .eq('race_date', '2026-02-09')\
        .eq('track_code', 'PRX')\
        .execute()
    
    results = query.data
    print(f"Found {len(results)} races for PRX on 2026-02-09.")
    
    cancelled_count = sum(1 for r in results if r['race_status'] == 'cancelled')
    print(f"Cancelled races found: {cancelled_count}")
    
    if cancelled_count > 0:
        print("PASS: Cancelled races are being returned.")
    else:
        print("FAIL: No cancelled races returned.")

if __name__ == "__main__":
    verify_past_races_query()
