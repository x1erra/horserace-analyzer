
import os
import json
from supabase_client import get_supabase_client
from dotenv import load_dotenv

load_dotenv()

def debug_pending_bets():
    try:
        supabase = get_supabase_client()
        
        # Get pending bets
        print("Fetching pending bets...")
        bets = supabase.table('hranalyzer_bets')\
            .select('*, hranalyzer_races(*, hranalyzer_race_entries(*))')\
            .eq('status', 'Pending')\
            .execute()
            
        print(f"Found {len(bets.data)} pending bets.")
        
        for bet in bets.data:
            print("-" * 50)
            print(f"Bet ID: {bet['id']}")
            print(f"Type: {bet['bet_type']}")
            print(f"Horse: {bet['horse_number']} - {bet['horse_name']}")
            
            race = bet.get('hranalyzer_races')
            if not race:
                print("RACE NOT FOUND FOR BET!")
                continue
                
            print(f"Race: {race['track_code']} Race {race['race_number']} ({race['race_date']})")
            print(f"Race Status: {race['race_status']}")
            
            if race['race_status'] != 'completed':
                print("-> Race is NOT completed. This explains why it is Pending.")
                continue
                
            # Race is completed, check entries
            entries = race.get('hranalyzer_race_entries', [])
            print(f"Total Entries: {len(entries)}")
            
            # Find the horse
            target_pgm = str(bet['horse_number'])
            found = False
            for entry in entries:
                e_pgm = str(entry['program_number'])
                # strict comparison as in backend.py
                if e_pgm == target_pgm:
                    found = True
                    print(f"MATCHING ENTRY FOUND:")
                    print(f"  Pgm: {entry['program_number']}")
                    print(f"  Name: {(entry.get('hranalyzer_horses') or {}).get('horse_name')}") # Note: nested might be shallow in this query
                    print(f"  Scratched: {entry.get('scratched')}")
                    print(f"  Finish: {entry.get('finish_position')}")
                    
                    if entry.get('scratched'):
                        print("-> ENTRY IS SCRATCHED. Logic should set status to 'Scratched'.")
                    elif not entry.get('finish_position'):
                         print("-> ENTRY HAS NO FINISH POSITION. Logic should set status to 'Loss'.")
                    else:
                         print("-> ENTRY HAS FINISH POSITION. Logic should settle.")
                    break
            
            if not found:
                print(f"-> NO ENTRY FOUND with program number '{target_pgm}'")
                print("Available numbers:", [str(e['program_number']) for e in entries])

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pending_bets()
