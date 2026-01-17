import requests
import json
import sys

BASE_URL = "http://localhost:5001/api"

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
        
        tc = race.get('track_code')
        rd = race.get('race_date')
        
        # DEBUG PRINT
        print(f"DEBUG: RaceKey={race_key}, TrackCode='{tc}' (len={len(tc) if tc else 0}), Date='{rd}'")
        print(f"DEBUG: Navigation={json.dumps(nav)}")
        
        return nav, tc, rd
    except Exception as e:
        print(f"Error fetching race details: {e}")
        return None, None, None

def main():
    print("Fetching races...")
    races = get_todays_races()
    
    # Filter for AQU
    aqu_races = [r for r in races if 'AQU' in r.get('track_code', '')]
    
    if not aqu_races:
        print("No AQU races found today. Fetching past races...")
        try:
             resp = requests.get(f"{BASE_URL}/past-races?limit=50")
             all_past = resp.json().get('races', [])
             aqu_races = [r for r in all_past if 'AQU' in r.get('track_code', '')]
        except Exception as e:
             print(f"Error fetching past races: {e}")

    if not aqu_races:
        print("No AQU races found at all.")
        return

    aqu_races.sort(key=lambda x: x['race_number'])
    
    print(f"Found {len(aqu_races)} AQU races:")
    for r in aqu_races:
        tc = r.get('track_code')
        # Print with quotes to see whitespace
        print(f" - Race {r['race_number']}: '{tc}' (len={len(tc)}) Key={r['race_key']}")
        
    # Check details for first 2 races
    if len(aqu_races) >= 2:
        print("\nChecking Race 1...")
        check_race_details(aqu_races[0]['race_key'])
        
        print("\nChecking Race 2...")
        check_race_details(aqu_races[1]['race_key'])

if __name__ == "__main__":
    main()
