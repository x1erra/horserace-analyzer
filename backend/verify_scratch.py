import os
import sys
# Add parent dir to path to find backend module if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend import get_supabase_client

try:
    supabase = get_supabase_client()
    print("Checking Dirty Diana...")
    
    # 1. Get Horse ID
    res_h = supabase.table('hranalyzer_horses').select('id, horse_name').eq('horse_name', 'Dirty Diana').execute()
    if not res_h.data:
        print("Horse 'Dirty Diana' not found in horses table.")
    else:
        horse_id = res_h.data[0]['id']
        print(f"Horse ID: {horse_id}")
        
        # 2. Get Entries
        # we want to see if she is scratched in any race
        res_e = supabase.table('hranalyzer_race_entries').select('*').eq('horse_id', horse_id).execute()
        
        print("\n--- Entries ---")
        for entry in res_e.data:
            # Get race info for context
            race_id = entry['race_id']
            res_r = supabase.table('hranalyzer_races').select('*').eq('id', race_id).execute()
            race_info = res_r.data[0] if res_r.data else {'race_date': '?', 'track_code': '?', 'race_number': '?'}
            
            print(f"Date: {race_info.get('race_date')} | Track: {race_info.get('track_code')} R{race_info.get('race_number')} | Scratched: {entry.get('scratched')} | Finish: {entry.get('finish_position')}")

    # 3. Check Bets
    res_bets = supabase.table('hranalyzer_bets').select('*').eq('horse_name', 'Dirty Diana').execute()
    print("\n--- Bets ---")
    for bet in res_bets.data:
         print(f"ID: {bet.get('id')} | Status: {bet.get('status')} | Selection: {bet.get('selection')} | Cost: {bet.get('bet_cost')}")

except Exception as e:
    import traceback
    traceback.print_exc()
