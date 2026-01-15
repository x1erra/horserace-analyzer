
import sys
import os
from datetime import datetime
import pytz

# Mock logic from backend.py to test it isolated
def test_next_post_logic():
    print("Testing Next Post Logic...")
    
    # Mock Data
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Case 1: Past Race (Should be ignored or handled)
    # Backend Logic: "Update next race time (Find the FIRST upcoming race that is in the future)"
    
    # We simulate the loop in backend.py
    
    # Mock Filtered Races (ordered by race number)
    races = [
        {'race_number': 1, 'race_status': 'completed', 'post_time': '12:00 PM'},
        {'race_number': 2, 'race_status': 'upcoming', 'post_time': '1:00 PM'}, # Past! (Assume now is 5 PM)
        {'race_number': 3, 'race_status': 'upcoming', 'post_time': '6:00 PM'}, # Future
    ]
    
    summary_map = {
        'TestTrack': {
            'next_race_iso': None,
            'next_race_time': None
        }
    }
    
    # Set "Now" to 5:00 PM EST
    est = pytz.timezone('America/New_York')
    # Use a fixed date for testing logic
    # Assume today is 2026-01-15 (from user metadata)
    # Time is 17:43 (5:43 PM)
    
    # Let's use the actual current time from system to verify strict behavior
    now_utc = datetime.now(pytz.utc)
    now_est = now_utc.astimezone(est)
    
    print(f"Current Admin Time: {now_est}")
    
    for r in races:
        if r['race_status'] == 'completed':
            continue
            
        name = 'TestTrack'
        
        if summary_map[name]['next_race_iso'] is None:
            post_time_str = r.get('post_time')
            if post_time_str:
                 try:
                     clean_time_str = post_time_str.replace("Post Time", "").replace("Post time", "").strip()
                     clean_time_str = clean_time_str.replace("ET", "").strip()
                     
                     pt = datetime.strptime(clean_time_str, "%I:%M %p").time()
                     
                     # Construct DT
                     # Use today's date
                     today_dt = datetime.now().date()
                     dt = datetime.combine(today_dt, pt)
                     
                     local_tz = pytz.timezone('America/New_York')
                     localized = local_tz.localize(dt)
                     
                     # THE FIX: Check if future
                     # Use a buffer? User said "doesn't show past times"
                     
                     if localized > now_est:
                         print(f"FOUND VALID NEXT RACE: Race {r['race_number']} at {localized}")
                         summary_map[name]['next_race_iso'] = localized.isoformat()
                         summary_map[name]['next_race_time'] = localized.strftime("%I:%M %p").lstrip('0')
                     else:
                         print(f"Skipping Race {r['race_number']} at {localized} (In the Past vs {now_est})")

                 except Exception as e:
                     print(f"Error: {e}")

    result = summary_map['TestTrack']
    print(f"Final Result: Next Race = {result['next_race_time']}")
    
    if result['next_race_time'] == '6:00 PM':
        print("SUCCESS: Skipped past race (1:00 PM) and picked future race (6:00 PM)")
    else:
        print("FAILURE: Did not pick expected race.")

if __name__ == "__main__":
    test_next_post_logic()
