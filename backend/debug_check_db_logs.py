
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

# Hand-rolled dotenv loading
def load_env_manual():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    print(f"Loading .env from: {os.path.abspath(env_path)}")
    if not os.path.exists(env_path):
        print("Error: .env file not found")
        return

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    os.environ[key.strip()] = value
    except Exception as e:
        print(f"Failed to load .env: {e}")

load_env_manual()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE keys not set")
    sys.exit(1)

def check_logs():
    try:
        url = f"{SUPABASE_URL}/rest/v1/hranalyzer_crawl_logs"
        params = {
            "select": "*",
            "order": "completed_at.desc",
            "limit": "10"
        }
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"Querying: {full_url}")
        
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            if data:
                print(f"Found {len(data)} log entries:")
                for log in data:
                    print(f"- Date: {log.get('crawl_date')}, Status: {log.get('status')}, Completed: {log.get('completed_at')}, Races: {log.get('races_updated')}, Error: {log.get('error_message')}")
            else:
                print("No log entries found.")

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode()
            print(f"Error body: {error_body}")
        except:
            pass
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    check_logs()
