
import os
import sys
from datetime import date
from supabase_client import get_supabase_client

def inspect_race():
    supabase = get_supabase_client()
    today = "2026-01-18"
    
    print(f"Inspecting races for {today}...")
    
    # Fetch Aqueduct Race 1
    response = supabase.table('hranalyzer_races')\
        .select('*, hranalyzer_tracks(track_name)')\
        .eq('race_date', today)\
        .eq('race_number', 1)\
        .execute()
        
    races = response.data
    for race in races:
        track_name = race.get('hranalyzer_tracks', {}).get('track_name') or race['track_code']
        if track_name == 'Aqueduct':
            print(f"\nFound Aqueduct Race 1 (ID: {race['id']})")
            print(f"Status in DB: {race['race_status']}")
            
            # Check entries
            entries = supabase.table('hranalyzer_race_entries')\
                .select('finish_position, program_number, scratched')\
                .eq('race_id', race['id'])\
                .execute()
                
            print("Entries:")
            has_results = False
            for e in entries.data:
                print(f"  PGM: {e['program_number']}, Fin: {e['finish_position']}, Scr: {e['scratched']}")
                if e['finish_position'] in [1, 2, 3]:
                    has_results = True
            
            print(f"Has Results (1-3): {has_results}")
            
    # Fetch Sam Houston Race 2
    response = supabase.table('hranalyzer_races')\
        .select('*, hranalyzer_tracks(track_name)')\
        .eq('race_date', today)\
        .eq('race_number', 2)\
        .execute()
        
    races = response.data
    for race in races:
        track_name = race.get('hranalyzer_tracks', {}).get('track_name') or race['track_code']
        # HOU name might vary
        if 'Houston' in track_name:
            print(f"\nFound Sam Houston Race 2 (ID: {race['id']})")
            print(f"Status in DB: {race['race_status']}")
             # Check entries
            entries = supabase.table('hranalyzer_race_entries')\
                .select('finish_position, program_number, scratched')\
                .eq('race_id', race['id'])\
                .execute()
                
            print("Entries:")
            has_results = False
            for e in entries.data:
                print(f"  PGM: {e['program_number']}, Fin: {e['finish_position']}, Scr: {e['scratched']}")
                if e['finish_position'] in [1, 2, 3]:
                    has_results = True
            print(f"Has Results (1-3): {has_results}")

if __name__ == "__main__":
    inspect_race()
