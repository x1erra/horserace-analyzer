from supabase_client import get_supabase_client
import sys

def check_feb9():
    supabase = get_supabase_client()
    print("Checking PRX races for 2026-02-09...")
    res = supabase.table('hranalyzer_races')        .select('race_number, race_status, is_cancelled')        .eq('track_code', 'PRX')        .eq('race_date', '2026-02-09')        .execute()
    
    for r in sorted(res.data, key=lambda x: x['race_number']):
        print(f"Race {r['race_number']}: status={r['race_status']}, is_cancelled={r['is_cancelled']}")

if __name__ == '__main__':
    check_feb9()
