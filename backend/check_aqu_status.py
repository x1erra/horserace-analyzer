
from supabase_client import get_supabase_client
import sys

def check_race():
    supabase = get_supabase_client()
    
    # Aqueduct is usually AQU
    # Date 2026-01-18
    # Race 1
    
    # Check ALL races for AQU 2026-01-18
    print("\n--- Checking ALL AQU Races for 2026-01-18 ---")
    races = supabase.table('hranalyzer_races')\
        .select('*')\
        .eq('track_code', 'AQU')\
        .eq('race_date', '2026-01-18')\
        .execute()
        
    for r in races.data:
        print(f"Race {r['race_number']} Status: {r['race_status']} (ID: {r['id']})")

    # Check for ANY cancelled race today
    print("\n--- Checking ANY Cancelled Races for 2026-01-18 ---")
    cancelled = supabase.table('hranalyzer_races')\
        .select('*')\
        .eq('race_date', '2026-01-18')\
        .eq('race_status', 'cancelled')\
        .execute()
        
    for r in cancelled.data:
        print(f"CANCELLED: {r['track_code']} Race {r['race_number']} (ID: {r['id']})")

if __name__ == "__main__":
    check_race()
