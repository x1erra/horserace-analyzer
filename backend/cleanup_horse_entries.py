"""
Script to investigate and clean garbage horses that have race entries.
These are parsing errors where dollar amounts were stored as horse names.
"""
import os
import re
from supabase_client import get_supabase_client

def is_garbage_name(name):
    """Check if a horse name is garbage that should be removed."""
    if not name:
        return True
    
    name = name.strip()
    
    # Too short
    if len(name) < 2:
        return True
    
    # Starts with $ or - (money amounts or dashes)
    if name.startswith('$') or name.startswith('-'):
        return True
    
    # Just numbers and punctuation (prices, amounts)
    if re.match(r'^[\d\s\.\,\-\$\%\(\)]+$', name):
        return True
    
    # Contains only special characters
    if re.match(r'^[\W\d]+$', name):
        return True
    
    # Common garbage patterns
    garbage_patterns = [
        r'^N/A$', r'^Unknown$', r'^TBD$', r'^--$',
        r'^\d+$',  # Just numbers
        r'^\d+\.\d+$',  # Decimal numbers
        r'^[\d,]+$',  # Numbers with commas
    ]
    for pattern in garbage_patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return True
    
    return False


def main():
    supabase = get_supabase_client()
    
    print("=" * 60)
    print("INVESTIGATING GARBAGE HORSES WITH RACE ENTRIES")
    print("=" * 60)
    
    # Fetch all horse names
    print("\nFetching all horses...")
    response = supabase.table('hranalyzer_horses').select('id, horse_name').execute()
    all_horses = response.data
    
    # Find garbage horses
    garbage_horses = [h for h in all_horses if is_garbage_name(h.get('horse_name', ''))]
    garbage_ids = [h['id'] for h in garbage_horses]
    
    print(f"Total garbage horses remaining: {len(garbage_horses)}")
    
    if not garbage_ids:
        print("No garbage horses found! Database is clean.")
        return
    
    # Get race entries for these garbage horses
    print("\nFetching race entries for garbage horses...")
    entries_response = supabase.table('hranalyzer_race_entries')\
        .select('''
            id, horse_id, program_number, race_id,
            race:hranalyzer_races(race_key, race_date, track_code, race_number)
        ''')\
        .in_('horse_id', garbage_ids)\
        .execute()
    
    print(f"Found {len(entries_response.data)} race entries linked to garbage horses")
    
    # Group entries by horse
    entries_by_horse = {}
    for entry in entries_response.data:
        hid = entry['horse_id']
        if hid not in entries_by_horse:
            entries_by_horse[hid] = []
        entries_by_horse[hid].append(entry)
    
    print("\n" + "=" * 60)
    print("GARBAGE HORSES WITH ENTRIES (DETAILS):")
    print("=" * 60)
    
    garbage_with_entries = [h for h in garbage_horses if h['id'] in entries_by_horse]
    
    for horse in garbage_with_entries:
        hid = horse['id']
        name = horse['horse_name']
        entries = entries_by_horse.get(hid, [])
        
        print(f"\n  Horse: '{name}' (ID: {hid[:8]}...)")
        print(f"  Race entries: {len(entries)}")
        for entry in entries[:3]:  # Show first 3
            race = entry.get('race') or {}
            print(f"    - {race.get('race_key', 'N/A')}: Post #{entry.get('program_number', '?')}")
        if len(entries) > 3:
            print(f"    ... and {len(entries) - 3} more")
    
    print("\n" + "=" * 60)
    print("CLEANUP OPTIONS:")
    print("=" * 60)
    print(f"1. DELETE race entries AND garbage horses ({len(entries_response.data)} entries, {len(garbage_with_entries)} horses)")
    print(f"2. Skip - leave them for manual review")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == '1':
        # Delete race entries first (due to foreign key)
        print(f"\nStep 1: Deleting {len(entries_response.data)} race entries...")
        entry_ids = [e['id'] for e in entries_response.data]
        for i in range(0, len(entry_ids), 50):
            batch = entry_ids[i:i + 50]
            try:
                supabase.table('hranalyzer_race_entries').delete().in_('id', batch).execute()
                print(f"  Deleted entries {i + len(batch)}/{len(entry_ids)}...")
            except Exception as e:
                print(f"  Error: {e}")
        
        # Now delete the garbage horses
        print(f"\nStep 2: Deleting {len(garbage_with_entries)} garbage horses...")
        horse_ids = [h['id'] for h in garbage_with_entries]
        for i in range(0, len(horse_ids), 50):
            batch = horse_ids[i:i + 50]
            try:
                supabase.table('hranalyzer_horses').delete().in_('id', batch).execute()
                print(f"  Deleted horses {i + len(batch)}/{len(horse_ids)}...")
            except Exception as e:
                print(f"  Error: {e}")
        
        print("\n✅ Cleanup complete!")
        
        # Re-count
        response = supabase.table('hranalyzer_horses').select('id', count='exact').execute()
        print(f"Remaining horses in database: {response.count}")
    else:
        print("\nSkipped. No changes made.")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
