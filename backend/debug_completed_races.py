from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    res = client.table('hranalyzer_races').select('id, race_key, race_status').eq('race_status', 'completed').execute()
    print(f"Total completed races found: {len(res.data)}")
    for r in res.data[:10]:
        print(f"Completed Race: {r['race_key']}")
        # Check entries for this specific race
        e_res = client.table('hranalyzer_race_entries').select('program_number, finish_position, hranalyzer_horses(horse_name)')\
            .eq('race_id', r['id']).eq('finish_position', 1).execute()
        if e_res.data:
            name = e_res.data[0].get('hranalyzer_horses', {}).get('horse_name', 'N/A')
            print(f"  -> Winner found: {name}")
        else:
            print(f"  -> NO WINNER FOUND in entries for this race.")

except Exception as e:
    print(f"Error: {e}")
