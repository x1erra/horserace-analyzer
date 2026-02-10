
from supabase_client import get_supabase_client
import json

def check_parx():
    supabase = get_supabase_client()
    
    # Check Feb 9 and 10
    dates = ['2026-02-09', '2026-02-10']
    
    for d in dates:
        print(f"\n--- Races for Parx Racing on {d} ---")
        res = supabase.table('hranalyzer_races')\
            .select('id, race_number, race_status, post_time, is_cancelled')\
            .eq('track_code', 'PRX')\
            .eq('race_date', d)\
            .order('race_number')\
            .execute()
        
        if not res.data:
            print("No races found.")
            continue
            
        for r in res.data:
            print(f"Race {r['race_number']}: status={r['race_status']}, cancelled={r['is_cancelled']}, post_time={r['post_time']}")

if __name__ == "__main__":
    check_parx()
