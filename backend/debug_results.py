import requests
import json

try:
    # URL might be localhost:5001 based on previous context, verify port from backend.py or trial
    # backend.py usually runs on 5001 or 5000. standard flask is 5000 but vite proxy often points to 5001. 
    # Let's try 5001 first as seen in frontend code.
    url = 'http://localhost:5001/api/todays-races'
    params = {'track': 'Fair Grounds', 'status': 'Completed'}
    
    print(f"Fetching {url} with params {params}...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        races = data.get('races', [])
        print(f"Found {len(races)} races.")
        
        if races:
            first_race = races[0]
            print("\n--- First Race Debug ---")
            print(f"ID: {first_race.get('id')}")
            print(f"Status: {first_race.get('race_status')}")
            print(f"Entry Count: {first_race.get('entry_count')}")
            print("Results Field:")
            print(json.dumps(first_race.get('results'), indent=2))
            
            if not first_race.get('results'):
                print("\nWARNING: 'results' field is empty!")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Exception: {e}")
