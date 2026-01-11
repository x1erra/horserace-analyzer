from supabase_client import get_supabase_client
import os

def check_one_race(client, race):
    winner_name = 'N/A'
    # 1. Try winning_horse relation
    if race.get('winning_horse'):
        winner_name = race['winning_horse'].get('horse_name', 'N/A')
        print(f"Winner from relation: {winner_name}")
    
    # 2. Fallback
    if winner_name == 'N/A':
        w_res = client.table('hranalyzer_race_entries')\
            .select('hranalyzer_horses(horse_name)')\
            .eq('race_id', race['id'])\
            .eq('finish_position', 1)\
            .execute()
        
        print(f"Fallback query result for {race['race_key']}: {w_res.data}")
        if w_res.data and w_res.data[0].get('hranalyzer_horses'):
            winner_name = w_res.data[0]['hranalyzer_horses'].get('horse_name', 'N/A')
            print(f"Winner from fallback: {winner_name}")
    return winner_name

try:
    client = get_supabase_client()
    from datetime import date
    today = date.today().isoformat()
    
    # Mirror the API query
    res = client.table('hranalyzer_races')\
        .select('*, hranalyzer_tracks(track_name, location), winning_horse:hranalyzer_horses(horse_name)')\
        .lt('race_date', today)\
        .order('race_date', desc=True)\
        .order('race_number', desc=False)\
        .in_('race_status', ['completed', 'past_drf_only'])\
        .limit(5).execute()
        
    print(f"Found {len(res.data)} races")
    for r in res.data:
        w = check_one_race(client, r)
        print(f"Race: {r['race_key']}, Winner: {w}")

except Exception as e:
    print(f"Error: {e}")
