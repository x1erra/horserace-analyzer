from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    tracks = ['GP', 'AQU', 'FG', 'TAM', 'HOU']
    race_date = '2026-01-04'
    
    for track in tracks:
        print(f"\n--- {track} - {race_date} ---")
        # Get Race 1 for each
        key = f"{track}-20260104-1"
        res = client.table('hranalyzer_races').select('id, race_status').eq('race_key', key).execute()
        
        if not res.data:
            print(f"Race {key} not found")
            continue
            
        race = res.data[0]
        print(f"Status: {race['race_status']}")
        
        # Check entries
        entries = client.table('hranalyzer_race_entries').select('program_number, finish_position, hranalyzer_horses(horse_name)')\
            .eq('race_id', race['id']).execute()
            
        winners = [e for e in entries.data if e.get('finish_position') == 1]
        print(f"Total Entries: {len(entries.data)}")
        if winners:
            name = winners[0].get('hranalyzer_horses', {}).get('horse_name', 'N/A')
            print(f"Winner: {name}")
        else:
            print("NO WINNER (pos=1) found in entries table!")

except Exception as e:
    print(f"Error: {e}")
