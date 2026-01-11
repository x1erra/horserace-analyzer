from supabase_client import get_supabase_client
from datetime import date

try:
    client = get_supabase_client()
    today = date.today().isoformat()
    
    # Check completed races
    res = client.table('hranalyzer_races').select('id', count='exact').eq('race_status', 'completed').execute()
    print(f"Completed races count: {res.count}")
    
    if res.count > 0:
        res_data = client.table('hranalyzer_races')\
            .select('race_key, race_status, winning_horse_id, final_time, hranalyzer_horses(horse_name)')\
            .eq('race_status', 'completed')\
            .limit(5)\
            .execute()
        print("\nSample completed races:")
        for r in res_data.data:
            winner = r.get('hranalyzer_horses', {}).get('horse_name', 'N/A') if r.get('hranalyzer_horses') else 'N/A'
            print(f"- {r['race_key']}: Status={r['race_status']}, Winner={winner}, Time={r['final_time']}")
    else:
        # Check all races to see what we have
        res_all = client.table('hranalyzer_races').select('id, race_key, race_status').limit(10).execute()
        print("\nSample of all races:")
        for r in res_all.data:
            print(f"- {r['race_key']}: Status={r['race_status']}")

except Exception as e:
    print(f"Error: {e}")
