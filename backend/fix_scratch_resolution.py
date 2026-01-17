from backend import get_supabase_client
from bet_resolution import resolve_all_pending_bets
import json

try:
    supabase = get_supabase_client()
    print("Fixing Dirty Diana Scratch Status...")
    
    # 1. Get Horse ID
    res_h = supabase.table('hranalyzer_horses').select('id').eq('horse_name', 'Dirty Diana').execute()
    if not res_h.data:
        print("Horse not found")
        exit()
    horse_id = res_h.data[0]['id']
    
    # 2. Update Entry
    # We want to update the entry for the specific race (GP R1 Jan 17).
    # First find the Race ID
    # Verify race date 2026-01-17 track GP number 1
    res_r = supabase.table('hranalyzer_races').select('id').eq('track_code', 'GP').eq('race_date', '2026-01-17').eq('race_number', 1).execute()
    if not res_r.data:
         print("Race not found")
         exit()
    race_id = res_r.data[0]['id']
    
    # Update
    res_up = supabase.table('hranalyzer_race_entries').update({'scratched': True}).eq('race_id', race_id).eq('horse_id', horse_id).execute()
    print(f"Update Result (Scratched=True): {len(res_up.data)} rows updated.")
    
    # 2.5 RESET BETS TO PENDING
    print("Resetting Dirty Diana bets to Pending...")
    bet_res = supabase.table('hranalyzer_bets').update({'status': 'Pending', 'payout': None}).eq('horse_name', 'Dirty Diana').execute()
    print(f"Reset {len(bet_res.data)} bets to Pending.")

    # 3. Trigger Resolution
    print("\nTriggering Bet Resolution...")
    result = resolve_all_pending_bets(supabase)
    print(f"Resolution Result: {json.dumps(result, indent=2)}")

except Exception as e:
    import traceback
    traceback.print_exc()
