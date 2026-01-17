"""
Script to analyze horse data in detail - investigate origin and validity.
"""
import os
from supabase_client import get_supabase_client
from collections import Counter

def main():
    supabase = get_supabase_client()
    
    print("=" * 70)
    print("HORSE DATABASE ANALYSIS")
    print("=" * 70)
    
    # 1. Get total horse count
    response = supabase.table('hranalyzer_horses').select('id', count='exact').execute()
    total_horses = response.count
    print(f"\nTotal horses in database: {total_horses}")
    
    # 2. Get horses WITH race entries (actually raced)
    entries_response = supabase.table('hranalyzer_race_entries').select('horse_id').execute()
    horses_with_entries = set(e['horse_id'] for e in entries_response.data)
    print(f"Horses with at least 1 race entry: {len(horses_with_entries)}")
    print(f"Horses with NO race entries (orphaned): {total_horses - len(horses_with_entries)}")
    
    # 3. Get date range of races
    print("\n" + "=" * 70)
    print("RACE DATE RANGE")
    print("=" * 70)
    date_response = supabase.table('hranalyzer_races')\
        .select('race_date')\
        .order('race_date')\
        .limit(1)\
        .execute()
    earliest = date_response.data[0]['race_date'] if date_response.data else 'N/A'
    
    date_response = supabase.table('hranalyzer_races')\
        .select('race_date')\
        .order('race_date', desc=True)\
        .limit(1)\
        .execute()
    latest = date_response.data[0]['race_date'] if date_response.data else 'N/A'
    
    print(f"Earliest race date: {earliest}")
    print(f"Latest race date: {latest}")
    
    # 4. Get track distribution
    print("\n" + "=" * 70)
    print("TRACK DISTRIBUTION")
    print("=" * 70)
    
    races_response = supabase.table('hranalyzer_races')\
        .select('track_code, race_status')\
        .execute()
    
    track_counts = Counter(r['track_code'] for r in races_response.data)
    completed_by_track = Counter(r['track_code'] for r in races_response.data if r['race_status'] == 'completed')
    
    print(f"{'Track':<10} {'Total Races':>12} {'Completed':>12}")
    print("-" * 36)
    for track in sorted(track_counts.keys()):
        print(f"{track:<10} {track_counts[track]:>12} {completed_by_track.get(track, 0):>12}")
    print(f"\nTotal tracks: {len(track_counts)}")
    
    # 5. Unique horse count per race
    print("\n" + "=" * 70)
    print("RACE ENTRIES ANALYSIS")
    print("=" * 70)
    
    # Get total race entries
    entries_count_response = supabase.table('hranalyzer_race_entries').select('id', count='exact').execute()
    total_entries = entries_count_response.count
    print(f"Total race entries: {total_entries}")
    print(f"Average entries per horse: {total_entries / len(horses_with_entries):.1f}" if horses_with_entries else "N/A")
    
    # 6. Sample some horse names to verify they look real
    print("\n" + "=" * 70)
    print("SAMPLE HORSE NAMES (random 30)")
    print("=" * 70)
    
    # Get a random sample by selecting from middle of alphabet
    sample_response = supabase.table('hranalyzer_horses')\
        .select('horse_name')\
        .gte('horse_name', 'M')\
        .lte('horse_name', 'N')\
        .limit(30)\
        .execute()
    
    for i, h in enumerate(sample_response.data, 1):
        print(f"  {i:2}. {h['horse_name']}")
    
    # 7. Check for duplicates
    print("\n" + "=" * 70)
    print("DUPLICATE CHECK")
    print("=" * 70)
    
    all_names = supabase.table('hranalyzer_horses').select('horse_name').execute()
    name_counts = Counter(h['horse_name'] for h in all_names.data)
    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    
    print(f"Total unique horse names: {len(name_counts)}")
    print(f"Names appearing more than once: {len(duplicates)}")
    
    if duplicates:
        print("\nTop 10 duplicate names:")
        for name, count in sorted(duplicates.items(), key=lambda x: -x[1])[:10]:
            print(f"  '{name}': {count} entries")
    
    # 8. Check for orphaned horses (no race entries)
    print("\n" + "=" * 70)
    print("ORPHANED HORSES (no race entries)")
    print("=" * 70)
    
    all_horse_ids = set(h['id'] for h in supabase.table('hranalyzer_horses').select('id').execute().data)
    orphaned_ids = all_horse_ids - horses_with_entries
    
    print(f"Horses without any race entries: {len(orphaned_ids)}")
    
    if orphaned_ids and len(orphaned_ids) > 0:
        # Get sample of orphaned horses
        orphan_sample = list(orphaned_ids)[:20]
        orphan_names = supabase.table('hranalyzer_horses')\
            .select('horse_name')\
            .in_('id', orphan_sample)\
            .execute()
        
        print("\nSample orphaned horse names:")
        for h in orphan_names.data:
            print(f"  - {h['horse_name']}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"""
  Total horses in DB:           {total_horses}
  With race entries (real):     {len(horses_with_entries)}
  Without race entries:         {len(orphaned_ids)}
  
  Race date range:              {earliest} to {latest}
  Total races:                  {len(races_response.data)}
  Unique tracks:                {len(track_counts)}
    """)


if __name__ == '__main__':
    main()
