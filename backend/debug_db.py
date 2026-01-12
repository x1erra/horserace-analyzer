from supabase_client import get_supabase_client
import json

try:
    supabase = get_supabase_client()
    
    # Get a completed race from today
    race = supabase.table('hranalyzer_races')\
        .select('id, track_code, race_number')\
        .eq('race_status', 'completed')\
        .eq('track_code', 'FG')\
        .limit(1)\
        .execute()
        
    if not race.data:
        print("No completed FG races found in DB.")
        exit()
        
    r = race.data[0]
    print(f"Checking race: {r['track_code']} #{r['race_number']} (ID: {r['id']})")
    
    # Check entries
    entries = supabase.table('hranalyzer_race_entries')\
        .select('program_number, finish_position, horse_id')\
        .eq('race_id', r['id'])\
        .execute()
        
    print(f"Found {len(entries.data)} entries.")
    for e in entries.data:
        print(f"#{e['program_number']}: Pos={e['finish_position']}")
        
except Exception as e:
    print(f"Error: {e}")
