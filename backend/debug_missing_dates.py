from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    
    print("--- CRAWL LOGS ---")
    crawl_logs = client.table('hranalyzer_crawl_logs').select('*').order('crawl_date', desc=True).limit(10).execute()
    for log in crawl_logs.data:
        print(f"Date: {log['crawl_date']}, Status: {log['status']}, Races Updated: {log.get('races_updated')}")
        
    print("\n--- RACES FOR JAN 4 ---")
    jan4_races = client.table('hranalyzer_races').select('race_key, race_status, data_source').eq('race_date', '2026-01-04').execute()
    for r in jan4_races.data:
        print(f"Key: {r['race_key']}, Status: {r['race_status']}, Source: {r['data_source']}")

    print("\n--- RACES FOR JAN 1 ---")
    jan1_races = client.table('hranalyzer_races').select('race_key, race_status, data_source').eq('race_date', '2026-01-01').execute()
    for r in jan1_races.data:
        print(f"Key: {r['race_key']}, Status: {r['race_status']}, Source: {r['data_source']}")

    print("\n--- RECENT COMPLETED RACES ---")
    comp_races = client.table('hranalyzer_races').select('race_key, race_date').eq('race_status', 'completed').order('race_date', desc=True).limit(5).execute()
    for r in comp_races.data:
        print(f"Key: {r['race_key']}, Date: {r['race_date']}")

except Exception as e:
    print(f"Error: {e}")
