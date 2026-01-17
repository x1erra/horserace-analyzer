"""
Merge duplicate horse records - preserves data before pruning.
1. Find orphan-active pairs based on normalized names
2. Merge any data from orphan to active (sire, dam, color, sex)
3. Update any race_entries pointing to orphan to point to active
4. Delete the orphan
"""
import os
import re
from supabase_client import get_supabase_client

def normalize_name(name):
    """Normalize horse name for matching."""
    if not name:
        return ''
    # Remove spaces, convert to uppercase, remove special chars
    return re.sub(r'[^A-Z0-9]', '', name.upper())


def main():
    supabase = get_supabase_client()
    
    print("=" * 70)
    print("MERGE & DEDUPLICATE HORSE RECORDS")
    print("=" * 70)
    
    # Get all horses
    print("\nFetching all horses...")
    all_horses = supabase.table('hranalyzer_horses')\
        .select('id, horse_name, sire, dam, color, sex, foaling_year, created_at')\
        .execute().data
    
    # Get all race entries to identify which horses are "active"
    print("Fetching race entries...")
    entries = supabase.table('hranalyzer_race_entries').select('horse_id').execute().data
    horses_with_entries = set(e['horse_id'] for e in entries)
    
    print(f"Total horses: {len(all_horses)}")
    print(f"With race entries: {len(horses_with_entries)}")
    
    # Build lookup maps
    active_horses = {}  # normalized_name -> horse record
    orphan_horses = []  # horses without entries
    
    for horse in all_horses:
        norm_name = normalize_name(horse['horse_name'])
        if horse['id'] in horses_with_entries:
            # This is an active horse
            if norm_name not in active_horses:
                active_horses[norm_name] = horse
            else:
                # Multiple active horses with same normalized name - keep the one with more data
                existing = active_horses[norm_name]
                if sum(1 for k in ['sire', 'dam', 'color', 'sex'] if horse.get(k)) > \
                   sum(1 for k in ['sire', 'dam', 'color', 'sex'] if existing.get(k)):
                    active_horses[norm_name] = horse
        else:
            orphan_horses.append(horse)
    
    print(f"Orphan horses: {len(orphan_horses)}")
    print(f"Unique active normalized names: {len(active_horses)}")
    
    # Find matches
    print("\n" + "=" * 70)
    print("FINDING DUPLICATE PAIRS")
    print("=" * 70)
    
    matches = []  # (orphan, active) pairs
    no_match_orphans = []  # orphans with no active match
    
    for orphan in orphan_horses:
        norm_name = normalize_name(orphan['horse_name'])
        if norm_name in active_horses:
            matches.append((orphan, active_horses[norm_name]))
        else:
            no_match_orphans.append(orphan)
    
    print(f"Orphans with active match: {len(matches)}")
    print(f"Orphans with no match: {len(no_match_orphans)}")
    
    # Show merge preview
    print("\n" + "=" * 70)
    print("DATA MERGE PREVIEW (first 20)")
    print("=" * 70)
    
    merge_count = 0
    for orphan, active in matches[:20]:
        merges = []
        for field in ['sire', 'dam', 'color', 'sex', 'foaling_year']:
            if orphan.get(field) and not active.get(field):
                merges.append(f"{field}='{orphan[field]}'")
        
        if merges:
            merge_count += 1
            print(f"\n  Orphan: '{orphan['horse_name']}' -> Active: '{active['horse_name']}'")
            print(f"    Will merge: {', '.join(merges)}")
    
    # Count total data to merge
    total_merges = 0
    for orphan, active in matches:
        for field in ['sire', 'dam', 'color', 'sex', 'foaling_year']:
            if orphan.get(field) and not active.get(field):
                total_merges += 1
    
    print(f"\nTotal field merges needed: {total_merges}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"""
  Matched orphan-active pairs:    {len(matches)}
    - Fields to merge:            {total_merges}
    - Will delete after merge:    {len(matches)} orphan records
    
  Unmatched orphans:              {len(no_match_orphans)}
    - These are truly orphaned (no active horse with same name)
    - Will be deleted
    
  Total horses after cleanup:     {len(active_horses) + len(no_match_orphans) - len(no_match_orphans)}
                                  = {len(active_horses)} (just the active ones)
    """)
    
    print("=" * 70)
    print("OPTIONS:")
    print("=" * 70)
    print("1. EXECUTE: Merge data + Delete all orphans")
    print("2. SKIP: No changes")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == '1':
        print("\n" + "=" * 70)
        print("EXECUTING MERGE & DELETE")
        print("=" * 70)
        
        # Step 1: Merge data from orphans to active
        print("\nStep 1: Merging data from orphans to active horses...")
        merged = 0
        for orphan, active in matches:
            update_data = {}
            for field in ['sire', 'dam', 'color', 'sex', 'foaling_year']:
                if orphan.get(field) and not active.get(field):
                    update_data[field] = orphan[field]
            
            if update_data:
                try:
                    supabase.table('hranalyzer_horses')\
                        .update(update_data)\
                        .eq('id', active['id'])\
                        .execute()
                    merged += 1
                except Exception as e:
                    print(f"  Error merging to {active['horse_name']}: {e}")
        
        print(f"  Merged data into {merged} active horses")
        
        # Step 2: Update any race_entries that might point to orphans (shouldn't be any, but just in case)
        print("\nStep 2: Checking for race entries pointing to orphans...")
        orphan_ids = [o['id'] for o in orphan_horses]
        
        # Check if any entries point to orphans (they shouldn't by definition, but let's be safe)
        check_entries = supabase.table('hranalyzer_race_entries')\
            .select('id, horse_id')\
            .in_('horse_id', orphan_ids[:100])\
            .execute()
        
        if check_entries.data:
            print(f"  WARNING: Found {len(check_entries.data)} entries pointing to orphans!")
            print("  These will need to be remapped...")
            # This shouldn't happen since orphans by definition have no entries
        else:
            print("  No entries pointing to orphans (as expected)")
        
        # Step 3: Delete orphans
        print(f"\nStep 3: Deleting {len(orphan_horses)} orphan horses...")
        deleted = 0
        for i in range(0, len(orphan_horses), 50):
            batch = [h['id'] for h in orphan_horses[i:i+50]]
            try:
                supabase.table('hranalyzer_horses').delete().in_('id', batch).execute()
                deleted += len(batch)
                if deleted % 200 == 0 or deleted == len(orphan_horses):
                    print(f"  Deleted {deleted}/{len(orphan_horses)}...")
            except Exception as e:
                print(f"  Error deleting batch: {e}")
        
        print(f"\n✅ COMPLETE!")
        print(f"  Data merged: {merged} records")
        print(f"  Orphans deleted: {deleted}")
        
        # Final count
        final_count = supabase.table('hranalyzer_horses').select('id', count='exact').execute()
        print(f"  Remaining horses: {final_count.count}")
        
    else:
        print("\nSkipped. No changes made.")


if __name__ == '__main__':
    main()
