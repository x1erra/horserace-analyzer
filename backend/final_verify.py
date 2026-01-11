from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    dates = ['2026-01-01', '2026-01-04']
    for d in dates:
        print(f"\n--- Results for {d} ---")
        res = client.table('hranalyzer_races').select('race_key, race_status, winning_horse_id')\
            .eq('track_code', 'GP').eq('race_date', d).execute()
        for r in res.data:
            print(f"Key: {r['race_key']}, Status: {r['race_status']}, WinnerID: {r.get('winning_horse_id')}")

except Exception as e:
    print(f"Error: {e}")
