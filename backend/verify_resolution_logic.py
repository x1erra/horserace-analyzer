
import logging
from supabase_client import get_supabase_client
from bet_resolution import resolve_all_pending_bets
import time

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_logic():
    try:
        supabase = get_supabase_client()
        
        # 1. Get a pending bet
        print("Fetching a pending bet...")
        bets = supabase.table('hranalyzer_bets').select('*, hranalyzer_races(id, race_status)').eq('status', 'Pending').limit(1).execute()
        
        if not bets.data:
            print("No pending bets found to test.")
            return
            
        bet = bets.data[0]
        bet_id = bet['id']
        race = bet['hranalyzer_races']
        race_id = race['id']
        original_status = race['race_status']
        
        print(f"Testing with Bet {bet_id} on Race {race_id} (Status: {original_status})")
        
        # 2. Mock Race as 'completed'
        print("Mocking race status to 'completed'...")
        supabase.table('hranalyzer_races').update({'race_status': 'completed'}).eq('id', race_id).execute()
        
        # 3. Mock Entry as Scratched (if not already)
        # Find entry for this horse
        horse_number = bet['horse_number']
        entries = supabase.table('hranalyzer_race_entries').select('id, scratched, finish_position').eq('race_id', race_id).eq('program_number', horse_number).execute()
        
        entry_id = None
        original_entry_data = None
        
        if entries.data:
            entry = entries.data[0]
            entry_id = entry['id']
            original_entry_data = entry
            print(f"Found entry {entry_id} (Scratched: {entry['scratched']})")
            
            # Allow logic to scratch it
            # But wait, if we want to test "Scratched" outcome, we must ensure it IS scratched.
            if not entry['scratched']:
                print("Mocking entry as Scratched...")
                supabase.table('hranalyzer_race_entries').update({'scratched': True, 'finish_position': None}).eq('id', entry_id).execute()
        else:
            print("Entry not found! Cannot test scratch logic fully if program number doesn't match.")
            
        # 4. Run Resolution
        print("Running resolve_all_pending_bets...")
        result = resolve_all_pending_bets(supabase)
        print("Result:", result)
        
        # 5. Verify Bet Status
        updated_bet = supabase.table('hranalyzer_bets').select('status').eq('id', bet_id).single().execute()
        print(f"Bet Status after resolution: {updated_bet.data['status']}")
        
        # 6. Cleanup / Revert
        print("Reverting changes...")
        supabase.table('hranalyzer_races').update({'race_status': original_status}).eq('id', race_id).execute()
        supabase.table('hranalyzer_bets').update({'status': 'Pending', 'payout': None}).eq('id', bet_id).execute()
        
        if entry_id and original_entry_data:
             supabase.table('hranalyzer_race_entries').update({
                 'scratched': original_entry_data['scratched'],
                 'finish_position': original_entry_data['finish_position']
             }).eq('id', entry_id).execute()
             
        print("Revert complete.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_logic()
