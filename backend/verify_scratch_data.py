
from supabase_client import get_supabase_client
import logging

# Setup basic logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_scratches():
    supabase = get_supabase_client()
    
    # 1. Count total scratched entries
    res = supabase.table('hranalyzer_race_entries')\
        .select('count', count='exact')\
        .eq('scratched', True)\
        .execute()
    
    total_scratches = res.count
    print(f"Total Scratched Entries in DB: {total_scratches}")

    if total_scratches == 0:
        print("WARNING: No scratched entries found. logic might be present but not producing data.")
        return

    # 2. Check for upcoming scratches (Pre-race)
    # Join with races to check status
    # Note: Supabase-js syntax via python client might need raw sql or careful filtering
    # We'll just fetch a few scratched entries and check their race status
    
    res_samples = supabase.table('hranalyzer_race_entries')\
        .select('id, program_number, scratched, race_id, hranalyzer_races(race_status, race_date, track_code)')\
        .eq('scratched', True)\
        .limit(10)\
        .execute()
        
    print("\nSample Scratched Entries:")
    upcoming_found = False
    completed_found = False
    
    for entry in res_samples.data:
        race = entry.get('hranalyzer_races')
        status = race.get('race_status') if race else 'unknown'
        print(f"- Race {race.get('track_code')} {race.get('race_date')} ({status}): Pgm {entry.get('program_number')}")
        
        if status == 'upcoming':
            upcoming_found = True
        elif status == 'completed':
            completed_found = True
            
    print("\nVerification Results:")
    print(f"Has Scratches for Completed Races: {completed_found}")
    print(f"Has Scratches for Upcoming Races: {upcoming_found}")

if __name__ == "__main__":
    verify_scratches()
