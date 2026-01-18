
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def check_null_counts():
    supabase = get_supabase_client()
    
    # Check nulls
    res = supabase.table('hranalyzer_claims')\
        .select('*', count='exact')\
        .is_('program_number', 'null')\
        .execute()
        
    total_res = supabase.table('hranalyzer_claims')\
        .select('*', count='exact')\
        .execute()
        
    count_null = res.count
    count_total = total_res.count
    
    print(f"Total Claims: {count_total}")
    print(f"Claims with NULL Program Number: {count_null}")
    
    if count_null > 0:
        print("\nSample of missing PGM claims:")
        for c in res.data[:5]:
            print(f" - {c['horse_name']} (Race ID: {c['race_id']})")

if __name__ == "__main__":
    check_null_counts()
