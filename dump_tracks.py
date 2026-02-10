
import os
import sys
from supabase_client import get_supabase_client

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def dump_tracks():
    supabase = get_supabase_client()
    try:
        response = supabase.table('hranalyzer_tracks').select('*').execute()
        for track in response.data:
            print(f"ID: {track['id']}, Code: {track['track_code']}, Name: {track['track_name']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_tracks()
