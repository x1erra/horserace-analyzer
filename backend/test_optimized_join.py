from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    
    # Try the optimized join
    # Select races and join entries where finish_position = 1 to get the winner name
    # We use a filter on the relation
    res = client.table('hranalyzer_races').select('*, winners:hranalyzer_race_entries(finish_position, horse:hranalyzer_horses(horse_name))')\
        .eq('winners.finish_position', 1)\
        .limit(5).execute()
        
    print(f"Races found: {len(res.data)}")
    for r in res.data:
        print(f"Race: {r['race_key']}")
        winners = r.get('winners', [])
        if winners:
            horse = winners[0].get('horse', {})
            name = horse.get('horse_name', 'N/A') if horse else 'N/A'
            print(f"  Winner from join: {name}")
        else:
            print("  No winner found in join results")

except Exception as e:
    print(f"Error: {e}")
