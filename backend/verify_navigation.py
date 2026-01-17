import requests
import json
import sys

BASE_URL = "https://api.trackdata.live/api"

def get_todays_races():
    try:
        resp = requests.get(f"{BASE_URL}/todays-races")
        resp.raise_for_status()
        return resp.json().get('races', [])
    except Exception as e:
        print(f"Error fetching today's races: {e}")
        return []

def check_race_details(race_key):
    try:
        url = f"{BASE_URL}/race-details/{race_key}"
        print(f"Fetching details for {race_key}...")
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        race = data.get('race', {})
        nav = data.get('navigation', {})
        
        print(f"Race: {race.get('track_code')} - Race {race.get('race_number')}")
        print(f"Navigation Data: {json.dumps(nav, indent=2)}")
        
        return nav
    except Exception as e:
        print(f"Error fetching race details: {e}")
        return None

def main():
    races = get_todays_races()
    if not races:
        print("No races found for today to test. Trying to fetch past races...")
        # Fallback to past races if today is empty
        try:
             resp = requests.get(f"{BASE_URL}/past-races?limit=5")
             races = resp.json().get('races', [])
        except Exception as e:
             print(f"Error fetching past races: {e}")

    if not races:
        print("No races found at all.")
        return

    # Try to find a track with multiple races
    tracks = {}
    for r in races:
        tc = r.get('track_code')
        if tc not in tracks:
            tracks[tc] = []
        tracks[tc].append(r)

    # Pick a track with > 1 race
    selected_track = None
    for tc, track_races in tracks.items():
        if len(track_races) > 1:
            selected_track = track_races
            break
            
    if not selected_track:
        print("Could not find a track with multiple races to test prev/next logic.")
        # Just test the first one available
        selected_track = [races[0]]

    # Sort by race number just in case
    selected_track.sort(key=lambda x: x['race_number'])
    
    # Test Middle Race (should have both)
    if len(selected_track) >= 3:
        target_race = selected_track[1] # The second race
        print(f"\nTesting Middle Race: Race {target_race['race_number']}")
        nav = check_race_details(target_race['race_key'])
        if nav:
            if nav.get('prev_race_key') and nav.get('next_race_key'):
                print("SUCCESS: Both Prev and Next keys are present.")
            else:
                print("FAILURE: Missing Prev or Next keys.")
    
    # Test First Race (should have no Prev)
    target_race = selected_track[0]
    print(f"\nTesting First Race: Race {target_race['race_number']}")
    nav = check_race_details(target_race['race_key'])
    if nav:
        if not nav.get('prev_race_key') and nav.get('next_race_key'):
             print("SUCCESS: No Prev key (correct) and Next key present.")
        elif nav.get('prev_race_key'):
             print("FAILURE: Prev key exists for first race.")
        else:
             print("Check: Next key might be missing if it's the only race or something else is wrong.")

    # Test Last Race (should have no Next)
    target_race = selected_track[-1]
    print(f"\nTesting Last Race: Race {target_race['race_number']}")
    nav = check_race_details(target_race['race_key'])
    if nav:
         if nav.get('prev_race_key') and not nav.get('next_race_key'):
              print("SUCCESS: Prev key present and No Next key (correct).")
         elif nav.get('next_race_key'):
              print("FAILURE: Next key exists for last race.")
         else:
              print("Check: Prev key might be missing if it's the only race.")

if __name__ == "__main__":
    main()
