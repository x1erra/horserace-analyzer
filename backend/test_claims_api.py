
import requests
import json

def test_claims_api():
    url = "http://localhost:5001/api/claims?limit=20"
    try:
        response = requests.get(url)
        data = response.json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Total claims in response: {len(data.get('claims', []))}")
        
        for i, claim in enumerate(data.get('claims', [])):
            print(f"Claim {i+1}: {claim.get('horse_name')} - Pgm: {claim.get('program_number')}")
            if i >= 10: break
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_claims_api()
