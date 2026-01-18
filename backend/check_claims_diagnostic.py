
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client
from crawl_equibase import normalize_name

def check_specific_claims():
    supabase = get_supabase_client()
    
    # Based on user screenshot
    claims_to_check = [
        {'horse': 'Confabulation', 'track': 'AQU', 'date': '2026-01-17', 'race': 1},
        {'horse': 'FTW Slam', 'track': 'FG', 'date': '2026-01-17', 'race': 4},
        {'horse': 'Del Mar Sunrise(IRE)', 'track': 'GP', 'date': '2026-01-17', 'race': 1},
        {'horse': 'Colonial Sense', 'track': 'GP', 'date': '2026-01-17', 'race': 1}
    ]
    
    for item in claims_to_check:
        print(f"\n--- Checking {item['horse']} ({item['track']} Race {item['race']} on {item['date']}) ---")
        
        # Find Race
        race_res = supabase.table('hranalyzer_races')\
            .select('id')\
            .eq('track_code', item['track'])\
            .eq('race_date', item['date'])\
            .eq('race_number', item['race'])\
            .execute()
            
        if not race_res.data:
            print(f"! Race not found in DB")
            continue
            
        race_id = race_res.data[0]['id']
        
        # Find Claim
        claim_res = supabase.table('hranalyzer_claims')\
            .select('*')\
            .eq('race_id', race_id)\
            .eq('horse_name', item['horse'])\
            .execute()
            
        if not claim_res.data:
            # Try searching by normalized name
            print(f"? Claim for '{item['horse']}' not found by exact name. Searching all claims in race...")
            all_claims = supabase.table('hranalyzer_claims').select('*').eq('race_id', race_id).execute()
            target_norm = normalize_name(item['horse'])
            for c in all_claims.data:
                if normalize_name(c['horse_name']) == target_norm:
                    print(f"  > Found claim: '{c['horse_name']}' (Pgm: {c['program_number']})")
                    break
            else:
                print(f"  ! No matching claim found in race.")
        else:
            c = claim_res.data[0]
            print(f"  Claim record: Horse='{c['horse_name']}', Pgm={c['program_number']}")
            
        # Check entries for matching
        entry_res = supabase.table('hranalyzer_race_entries')\
            .select('program_number, horse:hranalyzer_horses(horse_name)')\
            .eq('race_id', race_id)\
            .execute()
            
        if entry_res.data:
            print(f"  Entries in race ({len(entry_res.data)}):")
            target_norm = normalize_name(item['horse'])
            for e in entry_res.data:
                h_name = e['horse']['horse_name']
                norm_h = normalize_name(h_name)
                match_status = " <<< MATCH" if norm_h == target_norm else ""
                print(f"    - #{e['program_number']} \"{h_name}\" (norm: {norm_h}){match_status}")

if __name__ == "__main__":
    check_specific_claims()
