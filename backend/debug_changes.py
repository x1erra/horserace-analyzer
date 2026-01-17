import os
import sys
try:
    from backend.supabase_client import get_supabase_client
except ImportError:
    from supabase_client import get_supabase_client

def inspect_data():
    supabase = get_supabase_client()
    
    # 1. Inspect "A Lister" changes
    # First find the horse/entry to get ID
    print("--- SEARCHING 'A Lister' ---")
    horses = supabase.table('hranalyzer_horses').select('id, horse_name').eq('horse_name', 'A Lister').execute()
    
    if not horses.data:
        print("Horse 'A Lister' not found!")
    else:
        horse_id = horses.data[0]['id']
        print(f"Found Horse ID: {horse_id}")
        
        # Find entries
        entries = supabase.table('hranalyzer_race_entries').select('id, race_id, program_number').eq('horse_id', horse_id).execute()
        for ent in entries.data:
            eid = ent['id']
            rid = ent['race_id']
            print(f"Entry {eid} (Race {rid})")
            
            # Find changes for this entry
            changes = supabase.table('hranalyzer_changes').select('*').eq('entry_id', eid).execute()
            for ch in changes.data:
                print(f"  CHANGE: ID={ch['id']} Type={ch['change_type']} Desc='{ch['description']}'")

    # 2. Inspect 'Race-wide' / NULL entry changes
    print("\n--- SEARCHING NULL ENTRY CHANGES (Race-wide) ---")
    # Just grab a sample of recent ones
    null_changes = supabase.table('hranalyzer_changes').select('*').is_('entry_id', 'null').limit(20).order('created_at', desc=True).execute()
    
    for ch in null_changes.data:
        print(f"  CHANGE: ID={ch['id']} Type={ch['change_type']} Desc='{ch['description']}' RaceID={ch['race_id']}")

if __name__ == "__main__":
    inspect_data()
