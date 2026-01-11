from supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    # Try a simple join without single() or filters that might fail synchronously
    res = client.table('hranalyzer_race_entries')\
        .select('horse_id, finish_position, hranalyzer_horses(horse_name)')\
        .eq('finish_position', 1)\
        .limit(5)\
        .execute()
    
    print(f"Sample winners from entries table: {len(res.data)}")
    for r in res.data:
        horse = r.get('hranalyzer_horses', {})
        name = horse.get('horse_name', 'N/A') if horse else 'N/A'
        print(f"- Winner: {name}, Pos: {r['finish_position']}")

except Exception as e:
    print(f"Error: {e}")
