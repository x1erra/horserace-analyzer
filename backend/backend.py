import subprocess
import csv
from flask import Flask, jsonify
import json
import os
import glob
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def parse_csv_data(file_path):
    races = []
    try:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                track = row.get("track_name", "Unknown")
                date = row.get("race_date", "Unknown").replace("/", "")
                num = row.get("race_number", "0")
                unique_id = f"{track}-{date}-{num}"
                
                # Derive PDF URL from chart_url if possible, or use standard pattern
                # AQU-01042026-1 -> https://www.equibase.com/static/chart/pdf/AQU010426USA1.pdf
                # Note: This is an assumption based on Equibase patterns
                date_mmddyy = row.get("race_date", "").replace("/", "") # 01042026
                mm = date_mmddyy[:2]
                dd = date_mmddyy[2:4]
                yy = date_mmddyy[6:8]
                pdf_url = f"https://www.equibase.com/static/chart/pdf/{track}{mm}{dd}{yy}USA{num}.pdf"
                
                races.append({
                    "id": unique_id,
                    "name": f"Race {num} - {track}",
                    "date": row.get("race_date"),
                    "track": track,
                    "topPick": row.get("winning_horse", "Unknown"),
                    "winProb": 0,
                    "time": "N/A",
                    "payouts": row.get("payouts", ""),
                    "fractional_times": row.get("fractional_times", ""),
                    "chart_url": row.get("chart_url", ""),
                    "pdf_url": pdf_url
                })
    except Exception as e:
        print(f"Error parsing CSV: {e}")
    return {"races": races}

@app.route('/api/race-data')
def get_race_data():
    try:
        root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        csv_files = glob.glob(os.path.join(root_path, 'extract-data-*.csv'))
        if csv_files:
            latest_csv = max(csv_files, key=os.path.getctime)
            data = parse_csv_data(latest_csv)
            return jsonify(data)
        
        return jsonify({"error": "No data available"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/race-details/<race_id>')
def get_race_details(race_id):
    try:
        root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        csv_files = glob.glob(os.path.join(root_path, 'extract-data-*.csv'))
        if not csv_files:
            return jsonify({"error": "No data available"}), 404
            
        latest_csv = max(csv_files, key=os.path.getctime)
        data = parse_csv_data(latest_csv)
        
        # Find the specific race
        race = next((r for r in data["races"] if r["id"] == race_id), None)
        if not race:
            return jsonify({"error": "Race not found"}), 404
            
        # Check for detailed JSON
        details_file = os.path.join(root_path, 'backend', f'details-{race_id}.json')
        if os.path.exists(details_file):
            with open(details_file, 'r') as f:
                details = json.load(f)
                # Firecrawl output structure might vary, adjust accordingly
                # Assuming details contains the race object directly or in a list
                if isinstance(details, dict) and "data" in details:
                    race_data = details["data"]
                    if isinstance(race_data, dict) and "races" in race_data:
                        # Find the matching race number
                        specific_race = next((r for r in race_data["races"] if str(r.get("race_number")) == race_id.split('-')[-1]), None)
                        if specific_race:
                            race["horses"] = specific_race.get("horses", [])
                            race["detailed_info"] = specific_race
        
        return jsonify(race)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/crawl-race/<race_id>', methods=['POST'])
def crawl_race(race_id):
    try:
        root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        csv_files = glob.glob(os.path.join(root_path, 'extract-data-*.csv'))
        if not csv_files:
            return jsonify({"error": "No data available"}), 404
            
        latest_csv = max(csv_files, key=os.path.getctime)
        data = parse_csv_data(latest_csv)
        race = next((r for r in data["races"] if r["id"] == race_id), None)
        
        if not race or not race.get("pdf_url"):
            return jsonify({"error": "URL not found for this race"}), 400

        output_file = os.path.join(root_path, 'backend', f'details-{race_id}.json')
        crawler_script = os.path.join(root_path, 'backend', 'crawl_equibase.py')
        python_bin = os.path.join(root_path, 'venv', 'bin', 'python3')

        # Run the crawler as a subprocess
        result = subprocess.run([python_bin, crawler_script, race["pdf_url"], output_file], capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({"success": True, "message": "Crawling successful"})
        else:
            return jsonify({"error": "Crawling failed", "details": result.stderr}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)