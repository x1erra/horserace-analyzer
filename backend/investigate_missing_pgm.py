
import os
import sys
import re

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client
from crawl_equibase import normalize_name

def investigate():
    supabase = get_supabase_client()
    
    horses_to_check = [
        {'name': 'Slender Slipper', 'track': 'GP', 'date': '2026-01-16', 'race': 7},
        {'name': 'Sugar Magnolia', 'track': 'TAM', 'date': '2026-01-16', 'race': 9}
    ]
    
    for item in horses_to_check:
        print(f"\n--- Investigating {item['name']} ({item['track']} Race {item['race']} on {item['date']}) ---")
        
        # 1. Find the race
        res = supabase.table('hranalyzer_races')\
            .select('id')\
            .eq('track_code', item['track'])\
            .eq('race_date', item['date'])\
            .eq('race_number', item['race'])\
            .execute()
            
        if not res.data:
            print(f"Race not found for {item['track']} {item['date']} Race {item['race']}")
            continue
            
        rid = res.data[0]['id']
        print(f"Race ID: {rid}")
        
        # 2. Find the claim
        claim_res = supabase.table('hranalyzer_claims')\
            .select('*')\
            .eq('race_id', rid)\
            .execute()
            
        if not claim_res.data:
            print("No claims found for this race.")
        else:
            print(f"Claims found in race: {len(claim_res.data)}")
            for c in claim_res.data:
                print(f"  Claim: \"{c['horse_name']}\" (Pgm: {c['program_number']})")
                
        # 3. Find the race entries
        entry_res = supabase.table('hranalyzer_race_entries')\
            .select('program_number, horse:hranalyzer_horses(horse_name)')\
            .eq('race_id', rid)\
            .execute()
            
        if not entry_res.data:
            print("No race entries found for this race.")
        else:
            print(f"Entries found in race: {len(entry_res.data)}")
            norm_target = normalize_name(item['name'])
            print(f"Target normalized: \"{norm_target}\"")
            for e in entry_res.data:
                h_name = (e.get('horse') or {}).get('horse_name', 'Unknown')
                norm_h = normalize_name(h_name)
                print(f"  #{e['program_number']} \"{h_name}\" (norm: \"{norm_h}\")")
                if norm_h == norm_target:
                    print(f"    >>> MATCH FOUND! <<<")

if __name__ == "__main__":
    investigate()
