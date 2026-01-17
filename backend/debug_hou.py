
from supabase_client import get_supabase_client
from datetime import datetime
import pytz

def check_hou_race():
    supabase = get_supabase_client()
    today_str = datetime.now().strftime('%Y%m%d')
    race_key = f"HOU-{today_str}-9"
    
    print(f"Checking {race_key}...")
    res = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key).execute()
    
    if res.data:
        r = res.data[0]
        print(f"Status: {r.get('race_status')}")
        print(f"Post Time: {r.get('post_time')}")
        print(f"Results: {r.get('results_data')}")
    else:
        print("Race not found.")
        
    # Check Race 8 for context
    race_key_8 = f"HOU-{today_str}-8"
    res8 = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key_8).execute()
    if res8.data:
        r = res8.data[0]
        print(f"Race 8 Status: {r.get('race_status')}")

if __name__ == "__main__":
    check_hou_race()
