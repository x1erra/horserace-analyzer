import os
import sys
from supabase_client import get_supabase_client

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def update_track_timezones():
    print("Starting Track Timezone Fix...")
    supabase = get_supabase_client()
    
    try:
        # Known mappings
        timezone_map = {
            'TUP': 'America/Phoenix',        # Turf Paradise
            'SA': 'America/Los_Angeles',     # Santa Anita
            'FG': 'America/Chicago',         # Fair Grounds
            'GG': 'America/Los_Angeles',     # Golden Gate
            'OP': 'America/Chicago',         # Oaklawn
            'HOU': 'America/Chicago',        # Sam Houston
            'AQU': 'America/New_York',       # Aqueduct
            'GP': 'America/New_York',        # Gulfstream Park
            'TAM': 'America/New_York',       # Tampa Bay Downs
            'PRX': 'America/New_York',       # Parx
            'OAK': 'America/Chicago',        # Oaklawn 
            'TP': 'America/New_York',        # Turfway (Eastern)
            'PEN': 'America/New_York',       # Penn National
            'CT': 'America/New_York',        # Charles Town
            'MVR': 'America/New_York',       # Mahoning Valley
            'LRL': 'America/New_York',       # Laurel Park
            'DED': 'America/Chicago',        # Delta Downs
            'FON': 'America/Chicago',        # Fonner Park
            'HAW': 'America/Chicago',        # Hawthorne
            'SUN': 'America/Denver',         # Sunland Park (Mountain Time)
            'ZIA': 'America/Denver',         # Zia Park
            'RP': 'America/Chicago',         # Remington Park
            'WRD': 'America/Chicago',        # Will Rogers Downs
            'LAD': 'America/Chicago',        # Louisiana Downs
            'PRM': 'America/Chicago',        # Prairie Meadows
        }

        # Fetch all tracks
        response = supabase.table('hranalyzer_tracks').select('*').execute()
        tracks = response.data
        
        updates_made = 0
        
        for track in tracks:
            track_code = track['track_code']
            track_name = track['track_name']
            current_tz = track.get('timezone')
            
            # Use explicit mapping if present, otherwise default to NY
            correct_tz = timezone_map.get(track_code, 'America/New_York')
            
            if current_tz != correct_tz:
                print(f"Updating Track {track_code} ({track_name}): {current_tz} -> {correct_tz}")
                supabase.table('hranalyzer_tracks').update({'timezone': correct_tz}).eq('id', track['id']).execute()
                updates_made += 1
            
        print(f"\nCleanup Complete. {updates_made} track timezones updated.")
        
    except Exception as e:
        print(f"Error executing timezone update: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_track_timezones()
