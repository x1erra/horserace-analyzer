"""
Script to analyze and clean garbage horse names from the database.
Identifies patterns of invalid names and removes them.
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
    print("HORSE NAME CLEANUP ANALYSIS")
    print("=" * 60)
    
    # Fetch all horse names
    print("\nFetching all horses...")
    response = supabase.table('hranalyzer_horses').select('id, horse_name').execute()
    all_horses = response.data
    print(f"Total horses in database: {len(all_horses)}")
    
    # Categorize horses
    garbage_horses = []
    valid_horses = []
    
    for horse in all_horses:
        name = horse.get('horse_name', '')
        if is_garbage_name(name):
            garbage_horses.append(horse)
        else:
            valid_horses.append(horse)
    
    print(f"\nValid horse names: {len(valid_horses)}")
    print(f"Garbage horse names to remove: {len(garbage_horses)}")
    
    # Show sample of garbage names
    print("\n" + "=" * 60)
    print("SAMPLE GARBAGE NAMES (first 50):")
    print("=" * 60)
    for horse in garbage_horses[:50]:
        print(f"  ID: {horse['id'][:8]}... | Name: '{horse['horse_name']}'")
    
    if len(garbage_horses) > 50:
        print(f"  ... and {len(garbage_horses) - 50} more")
    
    # Check if any garbage horses have race entries
    print("\n" + "=" * 60)
    print("CHECKING FOR RACE ENTRIES ON GARBAGE HORSES...")
    print("=" * 60)
    
    garbage_ids = [h['id'] for h in garbage_horses]
    
    # Check in batches (Supabase has limits)
    horses_with_entries = []
    batch_size = 100
    for i in range(0, len(garbage_ids), batch_size):
        batch = garbage_ids[i:i + batch_size]
        entries_response = supabase.table('hranalyzer_race_entries')\
            .select('horse_id')\
            .in_('horse_id', batch)\
            .execute()
        
        if entries_response.data:
            found_ids = set(e['horse_id'] for e in entries_response.data)
            horses_with_entries.extend([h for h in garbage_horses if h['id'] in found_ids])
    
    print(f"Garbage horses WITH race entries (linked data): {len(horses_with_entries)}")
    
    # Show some examples of garbage horses with entries
    if horses_with_entries:
        print("\nExamples of garbage horses that have race entries:")
        for horse in horses_with_entries[:10]:
            print(f"  '{horse['horse_name']}' (ID: {horse['id'][:8]}...)")
    
    # Safe to delete: garbage horses WITHOUT race entries
    horses_with_entry_ids = set(h['id'] for h in horses_with_entries)
    safe_to_delete = [h for h in garbage_horses if h['id'] not in horses_with_entry_ids]
    
    print(f"\nGarbage horses safe to DELETE (no race entries): {len(safe_to_delete)}")
    
    # Ask for confirmation
    print("\n" + "=" * 60)
    print("CLEANUP OPTIONS:")
    print("=" * 60)
    print(f"1. DELETE {len(safe_to_delete)} orphaned garbage horses (no race entries)")
    print(f"2. Skip deletion (just analyze)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == '1':
        print(f"\nDeleting {len(safe_to_delete)} orphaned garbage horses...")
        deleted = 0
        for i in range(0, len(safe_to_delete), 50):
            batch = [h['id'] for h in safe_to_delete[i:i + 50]]
            try:
                supabase.table('hranalyzer_horses').delete().in_('id', batch).execute()
                deleted += len(batch)
                print(f"  Deleted {deleted}/{len(safe_to_delete)}...")
            except Exception as e:
                print(f"  Error deleting batch: {e}")
        
        print(f"\n✅ Successfully deleted {deleted} garbage horse records!")
        
        # Re-count
        response = supabase.table('hranalyzer_horses').select('id', count='exact').execute()
        print(f"Remaining horses in database: {response.count}")
    else:
        print("\nSkipped deletion. No changes made.")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
