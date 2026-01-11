from supabase_client import get_supabase_client
from datetime import date

try:
    client = get_supabase_client()
    
    # Check races with results (where winning_horse_id OR final_time is NOT NULL)
    res = client.table('hranalyzer_races').select('id, race_key, race_status, winning_horse_id, final_time')\
        .or_('winning_horse_id.not.is.null,final_time.not.is.null')\
        .limit(10).execute()
        
    print(f"Races with some result data: {len(res.data)}")
    for r in res.data:
        print(f"- {r['race_key']}: status={r['race_status']}, winner_id={r['winning_horse_id']}, time={r['final_time']}")

    # Check race entries for a completed race to see if finish_position is set
    sample_race_key = 'GP-20260111-2'
    race_id_res = client.table('hranalyzer_races').select('id').eq('race_key', sample_race_key).single().execute()
    if race_id_res.data:
        race_id = race_id_res.data['id']
        entries = client.table('hranalyzer_race_entries').select('program_number, finish_position, horse_id')\
            .eq('race_id', race_id).order('finish_position').execute()
        print(f"\nEntries for {sample_race_key}:")
        for e in entries.data:
            print(f"  PN {e['program_number']}: Finish={e['finish_position']}, HorseID={e['horse_id']}")

except Exception as e:
    print(f"Error: {e}")
