from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    
    # Try the optimized join for Jan 4
    res = client.table('hranalyzer_races').select('*, winners:hranalyzer_race_entries(finish_position, horse:hranalyzer_horses(horse_name))')\
        .eq('race_date', '2026-01-04')\
        .eq('winners.finish_position', 1)\
        .limit(10).execute()
        
    print(f"Races found: {len(res.data)}")
    for r in res.data:
        print(f"Race: {r['race_key']}")
        winners = r.get('winners', [])
        # Note: If no winner is found with finish_position=1, 'winners' will be an empty list [] due to the filter
        if winners:
            horse = winners[0].get('horse', {})
            name = horse.get('horse_name', 'N/A') if horse else 'N/A'
            print(f"  Winner from join: {name}")
        else:
            print("  No winner found in join results (finish_position=1 missing?)")

except Exception as e:
    print(f"Error: {e}")
