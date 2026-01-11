from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    
    # Dual join test
    # This might fail if aliasing doesn't work as expected with filters
    res = client.table('hranalyzer_races').select('''
        *, 
        track:hranalyzer_tracks(track_name),
        winner_entry:hranalyzer_race_entries(finish_position, horse:hranalyzer_horses(horse_name)),
        all_entries:hranalyzer_race_entries(id)
    ''')\
    .eq('race_date', '2026-01-04')\
    .eq('winner_entry.finish_position', 1)\
    .limit(5).execute()
        
    print(f"Races found: {len(res.data)}")
    for r in res.data:
        print(f"Race: {r['race_key']}")
        winners = r.get('winner_entry', [])
        winner_name = winners[0].get('horse', {}).get('horse_name', 'N/A') if winners else 'N/A'
        entry_count = len(r.get('all_entries', []))
        print(f"  Winner: {winner_name}, Count: {entry_count}")

except Exception as e:
    print(f"Error: {e}")
