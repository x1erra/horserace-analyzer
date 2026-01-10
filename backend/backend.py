"""
Flask Backend API for Horse Racing Analyzer
Provides endpoints for DRF PDF upload, race data retrieval, and Equibase crawling
"""

import os
import subprocess
from datetime import date, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from supabase_client import get_supabase_client

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        supabase = get_supabase_client()
        # Test connection
        supabase.table('hranalyzer_tracks').select('id').limit(1).execute()
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/upload-drf', methods=['POST'])
def upload_drf():
    """
    Upload and parse a DRF PDF file
    Returns: Parsed race data
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400

    try:
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Use sys.executable to get current python interpreter (works in venv and Docker)
        import sys
        python_bin = sys.executable
        parser_script = os.path.join(os.path.dirname(__file__), 'parse_drf.py')

        result = subprocess.run(
            [python_bin, parser_script, filepath],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Parse the output to get stats
            lines = result.stdout.strip().split('\n')
            races_parsed = 0
            entries_parsed = 0
            track_code = None
            race_date = None

            for line in lines:
                if 'Races parsed:' in line:
                    races_parsed = int(line.split(':')[1].strip())
                elif 'Entries parsed:' in line:
                    entries_parsed = int(line.split(':')[1].strip())
                elif 'Track:' in line:
                    track_code = line.split(':')[1].strip()
                elif 'Date:' in line:
                    race_date = line.split(':')[1].strip()

            return jsonify({
                'success': True,
                'message': f'Successfully parsed DRF PDF',
                'races_parsed': races_parsed,
                'entries_parsed': entries_parsed,
                'track_code': track_code,
                'race_date': race_date,
                'filename': filename
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to parse PDF',
                'details': result.stderr
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/todays-races', methods=['GET'])
def get_todays_races():
    """
    Get all races for today (upcoming races from DRF uploads)
    Returns: List of races with status='upcoming' for today's date
    """
    try:
        supabase = get_supabase_client()
        today = date.today().isoformat()

        # Get races for today
        response = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, location)')\
            .eq('race_date', today)\
            .eq('race_status', 'upcoming')\
            .order('race_number')\
            .execute()

        races = []
        for race in response.data:
            # Get entry count for each race
            entries_response = supabase.table('hranalyzer_race_entries')\
                .select('id', count='exact')\
                .eq('race_id', race['id'])\
                .execute()

            races.append({
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': race.get('hranalyzer_tracks', {}).get('track_name', race['track_code']),
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'purse': race['purse'],
                'entry_count': entries_response.count,
                'race_status': race['race_status']
            })

        return jsonify({
            'races': races,
            'count': len(races),
            'date': today
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/past-races', methods=['GET'])
def get_past_races():
    """
    Get past races with optional filters
    Query params:
    - track: Filter by track code (e.g., 'GP')
    - start_date: Filter races after this date (YYYY-MM-DD)
    - end_date: Filter races before this date (YYYY-MM-DD)
    - limit: Number of races to return (default 50)
    """
    try:
        supabase = get_supabase_client()

        # Get query parameters
        track = request.args.get('track')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))

        # Build query
        query = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, location)')\
            .in_('race_status', ['completed', 'past_drf_only'])

        if track:
            query = query.eq('track_code', track)
        if start_date:
            query = query.gte('race_date', start_date)
        if end_date:
            query = query.lte('race_date', end_date)

        response = query.order('race_date', desc=True)\
            .order('race_number')\
            .limit(limit)\
            .execute()

        races = []
        for race in response.data:
            # Get entry count
            entries_response = supabase.table('hranalyzer_race_entries')\
                .select('id', count='exact')\
                .eq('race_id', race['id'])\
                .execute()

            races.append({
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': race.get('hranalyzer_tracks', {}).get('track_name', race['track_code']),
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'purse': race['purse'],
                'entry_count': entries_response.count,
                'race_status': race['race_status'],
                'data_source': race['data_source']
            })

        return jsonify({
            'races': races,
            'count': len(races)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/race-details/<race_key>', methods=['GET'])
def get_race_details(race_key):
    """
    Get detailed information for a specific race
    Includes all entries with horse, jockey, trainer info
    Works for both upcoming and completed races
    """
    try:
        supabase = get_supabase_client()

        # Get race
        race_response = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, location, timezone)')\
            .eq('race_key', race_key)\
            .single()\
            .execute()

        if not race_response.data:
            return jsonify({'error': 'Race not found'}), 404

        race = race_response.data

        # Get all entries for this race
        entries_response = supabase.table('hranalyzer_race_entries')\
            .select('*, hranalyzer_horses(horse_name, sire, dam, color, sex)')\
            .eq('race_id', race['id'])\
            .order('program_number')\
            .execute()

        entries = []
        for entry in entries_response.data:
            entries.append({
                'program_number': entry['program_number'],
                'horse_name': entry['hranalyzer_horses']['horse_name'],
                'horse_info': {
                    'sire': entry['hranalyzer_horses'].get('sire'),
                    'dam': entry['hranalyzer_horses'].get('dam'),
                    'color': entry['hranalyzer_horses'].get('color'),
                    'sex': entry['hranalyzer_horses'].get('sex')
                },
                'jockey_id': entry['jockey_id'],
                'trainer_id': entry['trainer_id'],
                'morning_line_odds': entry['morning_line_odds'],
                'weight': entry['weight'],
                'medication': entry['medication'],
                'equipment': entry['equipment'],
                'scratched': entry['scratched'],
                # Result data (for completed races)
                'finish_position': entry['finish_position'],
                'final_odds': entry['final_odds'],
                'run_comments': entry['run_comments'],
                'win_payout': entry['win_payout'],
                'place_payout': entry['place_payout'],
                'show_payout': entry['show_payout']
            })

        # Get exotic payouts if this is a completed race
        exotic_payouts = []
        if race['race_status'] == 'completed':
            exotics_response = supabase.table('hranalyzer_exotic_payouts')\
                .select('*')\
                .eq('race_id', race['id'])\
                .execute()
            exotic_payouts = exotics_response.data

        return jsonify({
            'race': {
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': race.get('hranalyzer_tracks', {}).get('track_name', race['track_code']),
                'location': race.get('hranalyzer_tracks', {}).get('location'),
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'distance_feet': race['distance_feet'],
                'conditions': race['conditions'],
                'purse': race['purse'],
                'race_status': race['race_status'],
                'data_source': race['data_source'],
                'final_time': race['final_time'],
                'fractional_times': race['fractional_times'],
                'equibase_chart_url': race['equibase_chart_url'],
                'equibase_pdf_url': race['equibase_pdf_url']
            },
            'entries': entries,
            'exotic_payouts': exotic_payouts
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trigger-crawl', methods=['POST'])
def trigger_crawl():
    """
    Manually trigger Equibase crawler for a specific date
    Body: { "date": "2026-01-01" }
    """
    try:
        data = request.get_json()
        if not data or 'date' not in data:
            return jsonify({'error': 'Date required in request body'}), 400

        crawl_date = data['date']

        # Validate date format
        try:
            datetime.strptime(crawl_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Use sys.executable to get current python interpreter
        import sys
        python_bin = sys.executable
        crawler_script = os.path.join(os.path.dirname(__file__), 'crawl_equibase.py')

        result = subprocess.run(
            [python_bin, crawler_script, crawl_date],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'Crawler completed for {crawl_date}',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Crawler failed',
                'details': result.stderr
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Legacy endpoint for backwards compatibility (will be removed later)
@app.route('/api/race-data')
def get_race_data():
    """Legacy endpoint - redirects to /api/past-races"""
    return get_past_races()


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)