
import os
import sys
from datetime import date
from pprint import pprint

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client

def debug_changes():
    supabase = get_supabase_client()
    today = date.today().isoformat()
    
    # 1. Fetch from entries
    scratch_query = supabase.table('hranalyzer_race_entries')\
        .select('''
            id, program_number, scratched, updated_at,
            horse:hranalyzer_horses(horse_name),
            race:hranalyzer_races!inner(
                id, track_code, race_date, race_number, post_time
            )
        ''')\
        .eq('scratched', True)\
        .gte('race.race_date', today)
        
    entries_res = scratch_query.execute()
    entries_data = entries_res.data
    
    # 2. Fetch from changes
    changes_query = supabase.table('hranalyzer_changes')\
        .select('''
            id, change_type, description, change_time,
            entry:hranalyzer_race_entries(
                program_number,
                horse:hranalyzer_horses(horse_name)
            ),
            race:hranalyzer_races!inner(
                id, track_code, race_date, race_number
            )
        ''')\
        .gte('race.race_date', today)
        
    changes_res = changes_query.execute()
    changes_data = changes_res.data
    
    print(f"Found {len(entries_data)} scratches from entries table.")
    print(f"Found {len(changes_data)} changes from changes table.")
    
    # Combine and check for duplicates per horse
    combined = []
    
    for item in entries_data:
        race = item.get('race') or {}
        horse = item.get('horse') or {}
        combined.append({
            'source': 'entries',
            'track': race.get('track_code'),
            'race_num': race.get('race_number'),
            'horse': horse.get('horse_name'),
            'pgm': item.get('program_number'),
            'desc': 'Scratched'
        })
        
    for item in changes_data:
        race = item.get('race') or {}
        entry = item.get('entry') or {}
        horse = entry.get('horse') or {}
        combined.append({
            'source': 'changes',
            'track': race.get('track_code'),
            'race_num': race.get('race_number'),
            'horse': horse.get('horse_name', 'Race-wide'),
            'pgm': entry.get('program_number'),
            'desc': item.get('description'),
            'type': item.get('change_type')
        })
        
    # Group by key
    grouped = {}
    for c in combined:
        key = f"{c['track']}-{c['race_num']}-{c['horse']}"
        if key not in grouped: grouped[key] = []
        grouped[key].append(c)
        
    print("\n--- DUPLICATE GROUPS ---")
    for k, v in grouped.items():
        if len(v) > 1:
            print(f"Key: {k}")
            for item in v:
                print(f"  - {item['source']}: {item.get('type', 'N/A')} | {item['desc']}")
            print("")

if __name__ == "__main__":
    debug_changes()
