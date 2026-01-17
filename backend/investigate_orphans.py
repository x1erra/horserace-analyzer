"""
Deep investigation into orphaned horses - where did they come from?
"""
import os
from supabase_client import get_supabase_client
from collections import Counter

def main():
    supabase = get_supabase_client()
    
    print("=" * 70)
    print("DEEP INVESTIGATION: ORPHANED HORSES")
    print("=" * 70)
    
    # Get all horses
    all_horses = supabase.table('hranalyzer_horses').select('id, horse_name, created_at').execute().data
    all_horse_ids = {h['id']: h for h in all_horses}
    
    # Get all race entries
    entries = supabase.table('hranalyzer_race_entries').select('horse_id').execute().data
    horses_with_entries = set(e['horse_id'] for e in entries)
    
    # Find orphaned horses
    orphan_ids = set(all_horse_ids.keys()) - horses_with_entries
    orphaned_horses = [all_horse_ids[hid] for hid in orphan_ids]
    
    print(f"\nTotal horses: {len(all_horses)}")
    print(f"With race entries: {len(horses_with_entries)}")
    print(f"Orphaned: {len(orphaned_horses)}")
    
    # Analyze orphan creation dates
    print("\n" + "=" * 70)
    print("ORPHAN CREATION DATES")
    print("=" * 70)
    
    creation_dates = Counter()
    for h in orphaned_horses:
        date = h.get('created_at', 'Unknown')[:10] if h.get('created_at') else 'Unknown'
        creation_dates[date] += 1
    
    print(f"{'Date':<15} {'Count':>10}")
    print("-" * 25)
    for date in sorted(creation_dates.keys()):
        print(f"{date:<15} {creation_dates[date]:>10}")
    
    # Check for duplicates between orphaned and active horses (naming variations)
    print("\n" + "=" * 70)
    print("CHECKING FOR DUPLICATE NAMES (orphan vs active)")
    print("=" * 70)
    
    # Get names of horses WITH entries
    active_horses = supabase.table('hranalyzer_race_entries')\
        .select('horse_id, hranalyzer_horses(horse_name)')\
        .execute().data
    
    active_names = set()
    for e in active_horses:
        h = e.get('hranalyzer_horses')
        if h:
            active_names.add(h.get('horse_name', '').strip().upper())
    
    # Check orphan names against active names
    orphan_names = [h['horse_name'] for h in orphaned_horses]
    
    potential_dupes = []
    for name in orphan_names:
        normalized = name.strip().upper().replace(' ', '')
        for active in active_names:
            active_normalized = active.replace(' ', '')
            if normalized == active_normalized and name.upper() != active:
                potential_dupes.append((name, active))
    
    print(f"Potential duplicate/variant names found: {len(potential_dupes)}")
    if potential_dupes:
        print("\nExamples:")
        for orphan_name, active_name in potential_dupes[:20]:
            print(f"  Orphan: '{orphan_name}' <-> Active: '{active_name}'")
    
    # Sample orphaned horse names grouped by first letter
    print("\n" + "=" * 70)
    print("ORPHAN NAME PATTERNS")
    print("=" * 70)
    
    first_letter_counts = Counter(h['horse_name'][0].upper() if h['horse_name'] else '?' for h in orphaned_horses)
    
    print("Distribution by first letter:")
    for letter in sorted(first_letter_counts.keys()):
        bar = '#' * min(50, first_letter_counts[letter] // 5)
        print(f"  {letter}: {first_letter_counts[letter]:4d} {bar}")
    
    # Check if orphans look like real horse names
    print("\n" + "=" * 70)
    print("SAMPLE ORPHANED NAMES (100 random)")
    print("=" * 70)
    
    import random
    sample = random.sample(orphaned_horses, min(100, len(orphaned_horses)))
    for i, h in enumerate(sample, 1):
        print(f"  {i:3d}. {h['horse_name']}")
    
    # Check upload logs
    print("\n" + "=" * 70)
    print("UPLOAD LOGS (DRF PDFs)")
    print("=" * 70)
    
    try:
        uploads = supabase.table('hranalyzer_upload_logs').select('*').execute().data
        print(f"Total PDF uploads: {len(uploads)}")
        for u in uploads:
            print(f"  - {u.get('filename', 'N/A')}: {u.get('races_extracted', 0)} races, {u.get('entries_extracted', 0)} entries")
    except Exception as e:
        print(f"Could not fetch upload logs: {e}")


if __name__ == '__main__':
    main()
