
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client

def list_recent_claims():
    supabase = get_supabase_client()
    
    res = supabase.table('hranalyzer_claims')\
        .select('*, race:hranalyzer_races(track_code, race_date, race_number)')\
        .order('created_at', desc=True)\
        .limit(50)\
        .execute()
        
    if not res.data:
        print("No claims found.")
        return
        
    print(f"{'Date':<12} {'Track':<6} {'Race':<5} {'Horse':<25} {'Pgm':<5}")
    print("-" * 60)
    for c in res.data:
        race = c.get('race') or {}
        r_date = race.get('race_date', 'N/A')
        track = race.get('track_code', 'N/A')
        r_num = race.get('race_number', 'N/A')
        horse = c.get('horse_name', 'N/A')
        pgm = c.get('program_number', 'None')
        print(f"{r_date:<12} {track:<6} {r_num:<5} {horse:<25} {pgm:<5}")

if __name__ == "__main__":
    list_recent_claims()
