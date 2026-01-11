from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    # Check GP-20260104-3 specifically
    res = client.table('hranalyzer_races').select('id').eq('race_key', 'GP-20260104-3').single().execute()
    if res.data:
        race_id = res.data['id']
        entries = client.table('hranalyzer_race_entries').select('finish_position, hranalyzer_horses(horse_name)')\
            .eq('race_id', race_id).eq('finish_position', 1).execute()
        print(f"GP-20260104-3 Winner: {entries.data}")

    # Check GP-20260101-1
    res = client.table('hranalyzer_races').select('id').eq('race_key', 'GP-20260101-1').single().execute()
    if res.data:
        race_id = res.data['id']
        entries = client.table('hranalyzer_race_entries').select('finish_position, hranalyzer_horses(horse_name)')\
            .eq('race_id', race_id).eq('finish_position', 1).execute()
        print(f"GP-20260101-1 Winner: {entries.data}")

except Exception as e:
    print(f"Error: {e}")
