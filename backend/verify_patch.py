import sys
import os
from supabase_client import get_supabase_client

def verify():
    supabase = get_supabase_client()
    race_key = 'PRX-20260114-1'
    res = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key).execute()
    if res.data:
        race = res.data[0]
        print(f"Race: {race_key}")
        print(f"Post Time: {race.get('post_time')}")
        print(f"Purse: {race.get('purse')}")
        print(f"Status: {race.get('race_status')}")
    else:
        print(f"No data found for {race_key}")

if __name__ == "__main__":
    verify()
