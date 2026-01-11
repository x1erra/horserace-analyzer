from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    
    # Let's check GP-20260111-2 specifically
    # 1. Get the race id
    race_res = client.table('hranalyzer_races').select('id').eq('race_key', 'GP-20260111-2').single().execute()
    if not race_res.data:
        print("Race GP-20260111-2 not found")
    else:
        race_id = race_res.data['id']
        print(f"Race ID for GP-20260111-2: {race_id}")
        
        # 2. Check for winner entry
        winner_res = client.table('hranalyzer_race_entries')\
            .select('horse_id, finish_position, hranalyzer_horses(horse_name)')\
            .eq('race_id', race_id)\
            .eq('finish_position', 1)\
            .execute()
        
        print(f"Winner query data for {race_id}: {winner_res.data}")
        if winner_res.data:
            name = winner_res.data[0].get('hranalyzer_horses', {}).get('horse_name', 'N/A')
            print(f"Detected winner name: {name}")
        else:
            print("No winner (finish_position=1) found for this race in entries table.")

except Exception as e:
    print(f"Error: {e}")
