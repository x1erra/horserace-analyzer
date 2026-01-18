
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def check_duplicates():
    supabase = get_supabase_client()
    
    # Simple query to find horse_name, race_id combinations that appear more than once
    # We can't do GROUP BY easily in Supabase/PostgREST without RPC
    # So we'll just fetch all for a specific race where we saw issues
    
    issues = [
        {'track': 'AQU', 'date': '2026-01-17', 'race': 1}
    ]
    
    for item in issues:
        print(f"\n--- Checking duplicates in {item['track']} Race {item['race']} on {item['date']} ---")
        
        # Find Race
        race_res = supabase.table('hranalyzer_races')\
            .select('id')\
            .eq('track_code', item['track'])\
            .eq('race_date', item['date'])\
            .eq('race_number', item['race'])\
            .execute()
            
        if not race_res.data:
            print("Race not found")
            continue
            
        race_id = race_res.data[0]['id']
        
        # Find all claims for this race
        claims = supabase.table('hranalyzer_claims').select('*').eq('race_id', race_id).execute()
        
        counts = {}
        for c in claims.data:
            name = c['horse_name']
            counts[name] = counts.get(name, 0) + 1
            print(f"  Claim: '{name}' Pgm={c['program_number']} ID={c['id']}")
            
        for name, count in counts.items():
            if count > 1:
                print(f"!! DUPLICATE FOUND: '{name}' appears {count} times")

if __name__ == "__main__":
    check_duplicates()
