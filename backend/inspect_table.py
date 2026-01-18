
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def inspect_table():
    supabase = get_supabase_client()
    
    # We can't easily get column names without a raw SQL query or looking at the data
    # We'll just fetch one record and see all keys
    res = supabase.table('hranalyzer_claims').select('*').limit(1).execute()
    
    if res.data:
        print("Columns in hranalyzer_claims:")
        for key in res.data[0].keys():
            print(f"  - {key}: {res.data[0][key]} (type: {type(res.data[0][key])})")
    else:
        print("No data found in hranalyzer_claims.")

if __name__ == "__main__":
    inspect_table()
