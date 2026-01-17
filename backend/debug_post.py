
import os
from supabase_client import get_supabase_client
from dotenv import load_dotenv

def inspect_race():
    load_dotenv()
    client = get_supabase_client()
    
    # 1. Find the race
    print("Searching for race...")
    response = client.table('hranalyzer_races')\
        .select('*, hranalyzer_tracks(track_name)')\
        .eq('race_date', '2026-01-16')\
        .eq('race_number', 7)\
        .execute()
        
    race = None
    for r in response.data:
        t_name = r['hranalyzer_tracks']['track_name']
        print(f"Found race: {t_name} Race {r['race_number']} on {r['race_date']}")
        if 'Sam Houston' in t_name:
            race = r
            break
            
    if not race:
        print("Race not found!")
        return

    print(f"Inspecting Race ID: {race['id']}")
    
    # 2. Get entries
    entries = client.table('hranalyzer_race_entries')\
        .select('*, hranalyzer_horses(horse_name)')\
        .eq('race_id', race['id'])\
        .execute()
        
    print("\nEntries:")
    print(f"{'Post':<5} {'Horse':<20} {'Finish':<10} {'Data'}")
    print("-" * 60)
    for e in entries.data:
        horse = e['hranalyzer_horses']['horse_name']
        post = e['program_number']
        finish = e['finish_position']
        print(f"{str(post):<5} {horse:<20} {str(finish):<10} {e}")

if __name__ == "__main__":
    inspect_race()
