
import os
from supabase_client import get_supabase_client

def check_post_times():
    supabase = get_supabase_client()
    
    # query recent races
    print("Checking recent races for NULL post times...")
    res = supabase.table('hranalyzer_races') \
        .select('*') \
        .order('race_date', desc=True) \
        .limit(20) \
        .execute()
        
    for race in res.data:
        print(f"Date: {race['race_date']}, Track: {race['track_code']}, Race: {race['race_number']}, Post Time: {race['post_time']}")

if __name__ == "__main__":
    check_post_times()
