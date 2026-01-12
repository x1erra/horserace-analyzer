
import os
import sys
from datetime import date, datetime
import pytz
from supabase_client import get_supabase_client

# Mock Flask app config/context if needed, but we just need logic
def test_dashboard_logic():
    try:
        supabase = get_supabase_client()
        # Use today's date or override to test specific date
        today = date.today().isoformat()
        print(f"Testing for date: {today}")

        # 3. Get detailed summary for TODAY
        print("Executing query...")
        today_response = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, timezone), hranalyzer_race_entries(finish_position, hranalyzer_horses(horse_name))')\
            .eq('race_date', today)\
            .order('race_number')\
            .execute()
        
        print(f"Query successful. Rows returned: {len(today_response.data)}")
        
        summary_map = {}
        
        for r in today_response.data:
            name = r.get('hranalyzer_tracks', {}).get('track_name', r['track_code'])
            if name not in summary_map:
                summary_map[name] = {
                    'track_name': name,
                    'track_code': r['track_code'],
                    'total': 0,
                    'upcoming': 0,
                    'completed': 0,
                    'next_race_time': None,
                    'last_race_winner': None,
                    'last_race_number': 0
                }
            
            summary_map[name]['total'] += 1
            
            if r['race_status'] == 'completed':
                summary_map[name]['completed'] += 1
                if r['race_number'] > summary_map[name]['last_race_number']:
                    summary_map[name]['last_race_number'] = r['race_number']
                    winner_entry = next((e for e in r.get('hranalyzer_race_entries', []) if e['finish_position'] == 1), None)
                    if winner_entry and winner_entry.get('hranalyzer_horses'):
                        summary_map[name]['last_race_winner'] = winner_entry['hranalyzer_horses']['horse_name']
                    else:
                        summary_map[name]['last_race_winner'] = "Unknown"
                        
            else:
                summary_map[name]['upcoming'] += 1
                if summary_map[name]['next_race_time'] is None:
                    post_time_str = r.get('post_time')
                    if post_time_str:
                         try:
                             # Logic test
                             if len(post_time_str.split(':')) == 2:
                                 pt = datetime.strptime(post_time_str, "%H:%M").time()
                             else:
                                 pt = datetime.strptime(post_time_str, "%H:%M:%S").time()
                                 
                             today_dt = datetime.strptime(today, "%Y-%m-%d").date()
                             dt = datetime.combine(today_dt, pt)
                             
                             tz_name = r.get('hranalyzer_tracks', {}).get('timezone', 'America/New_York')
                             if not tz_name: tz_name = 'America/New_York'
                             
                             local_tz = pytz.timezone(tz_name)
                             localized = local_tz.localize(dt)
                             
                             summary_map[name]['next_race_iso'] = localized.isoformat()
                             summary_map[name]['next_race_time'] = localized.strftime("%I:%M %p").lstrip('0')
                             print(f"Parsed time for {name}: {summary_map[name]['next_race_time']}")
                         except Exception as e:
                             print(f"Error parsing time {post_time_str}: {e}")
                             summary_map[name]['next_race_time'] = post_time_str
        
        print("Success! Summary map keys: ", list(summary_map.keys()))

    except Exception as e:
        print("FAILED")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dashboard_logic()
