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
import traceback
import pytz

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
        traceback.print_exc()
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

        # Create upload log entry
        supabase = get_supabase_client()
        upload_log = supabase.table('hranalyzer_upload_logs').insert({
            'filename': filename,
            'file_path': filepath,
            'file_size': os.path.getsize(filepath),
            'upload_status': 'parsing'
        }).execute()
        
        upload_log_id = upload_log.data[0]['id'] if upload_log.data else None

        # Use sys.executable to get current python interpreter (works in venv and Docker)
        import sys
        python_bin = sys.executable
        parser_script = os.path.join(os.path.dirname(__file__), 'parse_drf.py')
        
        # Prepare arguments
        args = [python_bin, parser_script, filepath]
        if upload_log_id:
            args.append(upload_log_id)

        result = subprocess.run(
            args,
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


@app.route('/api/uploads', methods=['GET'])
def get_recent_uploads():
    """Get list of recent DRF uploads"""
    try:
        supabase = get_supabase_client()
        limit = int(request.args.get('limit', 10))
        
        response = supabase.table('hranalyzer_upload_logs')\
            .select('*')\
            .order('uploaded_at', desc=True)\
            .limit(limit)\
            .execute()
            
        return jsonify({
            'uploads': response.data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/uploads/<filename>', methods=['GET'])
def serve_upload(filename):
    """Serve uploaded PDF file"""
    from flask import send_from_directory
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'error': 'File not found'}), 404


@app.route('/api/todays-races', methods=['GET'])
def get_todays_races():
    """
    Get all races for today (upcoming races from DRF uploads)
    Returns: List of races with status='upcoming' for today's date
    Query params:
    - track: Filter by track name (optional)
    - status: Filter by status (optional: 'Upcoming', 'Completed', 'All')
    """
    try:
        supabase = get_supabase_client()
        today = date.today().isoformat()
        
        track_filter = request.args.get('track')
        status_filter = request.args.get('status')

        # 1. Get ALL races for today first
        query = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, location)')\
            .eq('race_date', today)\
            .order('race_number')
            
        response = query.execute()
        raw_races = response.data

        if not raw_races:
            return jsonify({'races': [], 'count': 0, 'date': today})

        # 2. Batch fetch ALL entries for these races (Single Query Optimization)
        race_ids = [r['id'] for r in raw_races]
        
        entries_response = supabase.table('hranalyzer_race_entries')\
            .select('race_id, id, program_number, finish_position, hranalyzer_horses(horse_name)')\
            .in_('race_id', race_ids)\
            .execute()
            
        all_entries = entries_response.data

        # 3. Process entries in memory
        # Map: race_id -> { count: 0, results: [] }
        race_stats = {}
        for entry in all_entries:
            rid = entry['race_id']
            if rid not in race_stats:
                race_stats[rid] = {'count': 0, 'results': []}
            
            # Increment count
            race_stats[rid]['count'] += 1
            
            # Check for top 3 finish
            if entry.get('finish_position') in [1, 2, 3]:
                horse_name = entry.get('hranalyzer_horses', {}).get('horse_name', 'Unknown')
                race_stats[rid]['results'].append({
                    'position': entry['finish_position'],
                    'horse': horse_name,
                    'number': entry.get('program_number')
                })

        # Sort results by position for each race
        for rid in race_stats:
            race_stats[rid]['results'].sort(key=lambda x: x['position'])

        races = []
        for race in raw_races:
            track_name = race.get('hranalyzer_tracks', {}).get('track_name', race['track_code'])
            
            # Filter logic
            if track_filter and track_filter != 'All':
                 if track_name != track_filter and race['track_code'] != track_filter:
                     continue

            if status_filter and status_filter != 'All':
                if status_filter == 'Upcoming' and race['race_status'] == 'completed':
                    continue
                if status_filter == 'Completed' and race['race_status'] != 'completed':
                    continue

            # Get pre-calculated stats
            stats = race_stats.get(race['id'], {'count': 0, 'results': []})

            races.append({
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': track_name,
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'purse': race['purse'],
                'entry_count': stats['count'],
                'race_status': race['race_status'],
                'results': stats['results'], # Top 3 finishers
                'id': race['id']
            })

        return jsonify({
            'races': races,
            'count': len(races),
            'date': today
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    """
    Get all unique tracks and dates for filtering, plus today's summary
    Returns: { 
        tracks: [], 
        dates: [], 
        today_summary: [ { track_name, total, upcoming, completed } ] 
    }
    """
    try:
        supabase = get_supabase_client()
        today = date.today().isoformat()

        # 1. Get all distinct dates
        dates_response = supabase.table('hranalyzer_races')\
            .select('race_date')\
            .order('race_date', desc=True)\
            .execute()
        
        # Filter out future dates (ensure no future forward-filled dates appear in past filters)
        all_unique_dates = set(r['race_date'] for r in dates_response.data)
        unique_dates = sorted([d for d in all_unique_dates if d <= today], reverse=True)

        # 2. Get all distinct tracks (for historical filter)
        tracks_response = supabase.table('hranalyzer_races')\
            .select('track_code, hranalyzer_tracks(track_name)')\
            .execute()
            
        unique_tracks = {}
        for r in tracks_response.data:
            code = r['track_code']
            name = r.get('hranalyzer_tracks', {}).get('track_name', code)
            unique_tracks[name] = code 
        
        sorted_tracks = []
        for name in sorted(list(unique_tracks.keys())):
            sorted_tracks.append({
                'name': name,
                'code': unique_tracks[name]
            })

        # 3. Get detailed summary for TODAY
        today_response = supabase.table('hranalyzer_races')\
            .select('*, hranalyzer_tracks(track_name, timezone), hranalyzer_race_entries(finish_position, hranalyzer_horses(horse_name))')\
            .eq('race_date', today)\
            .order('race_number')\
            .execute()
            
        summary_map = {}
        
        # Helper to parse post time for sorting/comparison if needed (optional, here we trust race_number order)
        
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
                # Update last race winner (assuming races ordered by race_number)
                # Ensure we are actually looking at the latest race number processed
                if r['race_number'] > summary_map[name]['last_race_number']:
                    summary_map[name]['last_race_number'] = r['race_number']
                    # Find winner
                    winner_entry = next((e for e in r.get('hranalyzer_race_entries', []) if e['finish_position'] == 1), None)
                    if winner_entry and winner_entry.get('hranalyzer_horses'):
                        summary_map[name]['last_race_winner'] = winner_entry['hranalyzer_horses']['horse_name']
                    else:
                        summary_map[name]['last_race_winner'] = "Unknown"
                        
            else:
                summary_map[name]['upcoming'] += 1
                # Update next race time (first one we encounter that is upcoming, since we ordered by race_number)
                if summary_map[name]['next_race_time'] is None:
                    post_time_str = r.get('post_time')
                    if post_time_str:
                         try:
                             # Parse TIME (HH:MM:SS) and combine with today to get ISO string
                             # Handle cases where post_time_str might be HH:MM:SS or HH:MM
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
                         except Exception as e:
                             print(f"Error parsing time {post_time_str}: {e}")
                             summary_map[name]['next_race_time'] = post_time_str
                
        today_summary = sorted(list(summary_map.values()), key=lambda x: x['track_name'])

        return jsonify({
            'dates': unique_dates,
            'tracks': sorted_tracks,
            'today_summary': today_summary
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
        today = date.today().isoformat()

        # Get query parameters
        track = request.args.get('track')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))

        # Build query - strictly previous days
        # FETCH TOP 3 FINISHERS efficiently using the join
        # We rename the alias from 'winner_entry' to 'results' since it now holds more than just the winner
        query = supabase.table('hranalyzer_races')\
            .select('''
                *, 
                track:hranalyzer_tracks(track_name, location), 
                results:hranalyzer_race_entries(finish_position, program_number, horse:hranalyzer_horses(horse_name)),
                all_entries:hranalyzer_race_entries(id)
            ''')\
            .lte('race_date', today)\
            .order('race_date', desc=True)\
            .order('race_number', desc=False)\
            .in_('race_status', ['completed', 'past_drf_only'])

        # Filter the results join to only include top 3
        # Note: Supabase/PostgREST 'in' filter on joined resource syntax might vary or apply to all. 
        # Safest to fetch and filter in memory if the join filter is tricky, BUT:
        # We can try to filter the join: results(finish_position.in.(1,2,3)) logic is not standard PostgREST via select param easily.
        # Standard approach: Fetch all entries or rely on the client. 
        # However, for efficiency, fetching all entries for past races might be heavy if fully populated.
        # Let's try to trust the memory filter for now OR use the `select` syntax if possible.
        # Actually, let's keep it simple: Fetch TOP 3 if possible, or just parse in refined logic loop.
        # Warning: Filtering a relation in `select` string is not supported directly in this client syntax usually.
        # So we will fetch basic info and filter in Python. Top 3 is small enough.
        
        # NOTE: Just fetching all entries for valid races might be too much.
        # Optimization: We can't easily filter the nested resource in the SELECT string with the standard client without raw SQL.
        # Use previous strategy: Loop is okay if limit is 50. But we want "efficient".
        # Let's stick to the previous pattern but map it correctly.
        
        if track:
            query = query.eq('track_code', track)
        if start_date:
            query = query.gte('race_date', start_date)
        if end_date:
            query = query.lte('race_date', end_date)

        response = query.limit(limit).execute()

        races = []
        for race in response.data:
            results_data = race.get('results', [])
            # Filter for top 3 and format
            formatted_results = []
            winner_name = 'N/A'
            
            for r in results_data:
                pos = r.get('finish_position')
                if pos and pos in [1, 2, 3]:
                    horse_name = r.get('horse', {}).get('horse_name', 'Unknown')
                    formatted_results.append({
                        'position': pos,
                        'horse': horse_name,
                        'number': r.get('program_number')
                    })
                    if pos == 1:
                        winner_name = horse_name
            
            formatted_results.sort(key=lambda x: x['position'])

            races.append({
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': race.get('track', {}).get('track_name', race['track_code']),
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'purse': race['purse'],
                'entry_count': len(race.get('all_entries', [])),
                'race_status': race['race_status'],
                'data_source': race['data_source'],
                'id': race['id'],
                'winner': winner_name,
                'results': formatted_results, # Top 3
                'time': race.get('final_time') or 'N/A',
                'link': race.get('equibase_chart_url') or 'N/A'
            })

        return jsonify({
            'races': races,
            'count': len(races)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': 'Error in get_past_races'}), 500


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
        # Join with horses, jockeys, and trainers
        entries_response = supabase.table('hranalyzer_race_entries')\
            .select('''
                *, 
                hranalyzer_horses(horse_name, sire, dam, color, sex),
                hranalyzer_jockeys(jockey_name),
                hranalyzer_trainers(trainer_name)
            ''')\
            .eq('race_id', race['id'])\
            .order('program_number')\
            .execute()

        entries = []
        for entry in entries_response.data:
            # Safely get nested data
            horse_data = entry.get('hranalyzer_horses') or {}
            jockey_data = entry.get('hranalyzer_jockeys') or {}
            trainer_data = entry.get('hranalyzer_trainers') or {}

            entries.append({
                'program_number': entry['program_number'],
                'horse_name': horse_data.get('horse_name', 'Unknown'),
                'horse_info': {
                    'sire': horse_data.get('sire'),
                    'dam': horse_data.get('dam'),
                    'color': horse_data.get('color'),
                    'sex': horse_data.get('sex')
                },
                'jockey_id': entry['jockey_id'],
                'jockey_name': jockey_data.get('jockey_name', 'N/A'),
                'trainer_id': entry['trainer_id'],
                'trainer_name': trainer_data.get('trainer_name', 'N/A'),
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

        # Get exotic payouts and claims if this is a completed race
        exotic_payouts = []
        claims = []
        if race['race_status'] == 'completed':
            exotics_response = supabase.table('hranalyzer_exotic_payouts')\
                .select('*')\
                .eq('race_id', race['id'])\
                .execute()
            exotic_payouts = exotics_response.data
            
            claims_response = supabase.table('hranalyzer_claims')\
                .select('*')\
                .eq('race_id', race['id'])\
                .execute()
            claims = claims_response.data

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
            'exotic_payouts': exotic_payouts,
            'claims': claims
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/claims', methods=['GET'])
def get_claims():
    """
    Get claimed horses with optional filters
    Query params:
    - track: Filter by track code
    - start_date: Filter by date range
    - end_date: Filter by date range
    - limit: Limit results (default 100)
    """
    try:
        supabase = get_supabase_client()
        
        # Get query parameters
        track = request.args.get('track')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        
        # Select claims with race info
        query = supabase.table('hranalyzer_claims')\
            .select('*, hranalyzer_races(race_key, track_code, race_date, race_number, hranalyzer_tracks(track_name))')\
            .order('created_at', desc=True)\
            .limit(limit)
            
        response = query.execute()
        
        claims = []
        for item in response.data:
            race = item.get('hranalyzer_races')
            if not race:
                continue
            
            # Helper to access nested track name safely
            track_info = race.get('hranalyzer_tracks')
            track_name = track_info.get('track_name') if track_info else race['track_code']

            # Python-side filtering
            if track and race['track_code'] != track and track_name != track:
                continue
            if start_date and race['race_date'] < start_date:
                continue
            if end_date and race['race_date'] > end_date:
                continue
            
            claims.append({
                'id': item['id'],
                'race_key': race['race_key'],
                'race_date': race['race_date'],
                'track_code': race['track_code'],
                'track_name': track_name,
                'race_number': race['race_number'],
                'horse_name': item['horse_name'],
                'new_trainer': item['new_trainer_name'],
                'new_owner': item['new_owner_name'],
                'claim_price': item['claim_price']
            })
            
        return jsonify({
            'claims': claims,
            'count': len(claims)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets', methods=['POST'])
def place_bet():
    """Place a new bet"""
    try:
        data = request.get_json()
        race_id = data.get('race_id')
        horse_number = data.get('horse_number')
        horse_name = data.get('horse_name')
        bet_type = data.get('bet_type', 'Win')
        amount = data.get('amount', 2.00)

        if not race_id or not bet_type:
            return jsonify({'error': 'Missing required fields'}), 400

        supabase = get_supabase_client()
        
        # Verify race exists
        race = supabase.table('hranalyzer_races').select('id, race_status').eq('id', race_id).single().execute()
        if not race.data:
            return jsonify({'error': 'Race not found'}), 404

        # Insert bet
        bet = {
            'race_id': race_id,
            'horse_number': horse_number,
            'horse_name': horse_name,
            'bet_type': bet_type,
            'bet_amount': amount,
            'status': 'Pending'
        }
        
        response = supabase.table('hranalyzer_bets').insert(bet).execute()
        
        return jsonify({
            'success': True,
            'bet': response.data[0]
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets', methods=['GET'])
def get_bets():
    """Get all bets with race info"""
    try:
        supabase = get_supabase_client()
        limit = int(request.args.get('limit', 50))
        
        response = supabase.table('hranalyzer_bets')\
            .select('*, hranalyzer_races(race_key, race_number, race_date, track_code, race_status)')\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
            
        return jsonify({
            'bets': response.data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets/resolve', methods=['POST'])
def resolve_bets():
    """
    Check pending bets against completed races and resolve them.
    Can be triggered manually or by crawler.
    """
    try:
        supabase = get_supabase_client()
        
        # 1. Get all pending bets
        pending_bets = supabase.table('hranalyzer_bets')\
            .select('*, hranalyzer_races(race_status, id)')\
            .eq('status', 'Pending')\
            .execute()
            
        resolved_count = 0
        updated_bets = []
        
        for bet in pending_bets.data:
            race = bet.get('hranalyzer_races')
            if not race or race.get('race_status') != 'completed':
                continue
                
            # Race is completed! Check results.
            race_id = bet['race_id']
            horse_number = bet['horse_number']
            bet_type = bet['bet_type']
            
            # Fetch entries for this race to find the winner/payouts
            entries = supabase.table('hranalyzer_race_entries')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
                
            # Find the horse we bet on
            my_horse = next((e for e in entries.data if e['program_number'] == horse_number), None)
            
            if not my_horse:
                # Scratched or not found?
                # Check scratches
                # For now mark as Loss if not found, or maybe 'Void' if scratched logic strictly implemented
                # Simple logic: Loss
                new_status = 'Loss'
                payout = 0
            elif my_horse.get('scratched'):
                new_status = 'Scratched' # Refund usually
                payout = 0 # Or refund amount?
            else:
                new_status = 'Loss'
                payout = 0
                
                if bet_type == 'Win':
                    if my_horse.get('finish_position') == 1:
                        new_status = 'Win'
                        payout = my_horse.get('win_payout', 0) or 0
                elif bet_type == 'Place':
                    if my_horse.get('finish_position') in [1, 2]:
                        new_status = 'Win'
                        payout = my_horse.get('place_payout', 0) or 0
                elif bet_type == 'Show':
                    if my_horse.get('finish_position') in [1, 2, 3]:
                        new_status = 'Win'
                        payout = my_horse.get('show_payout', 0) or 0
                        
                # Handle multiplier (payouts are usually for $2 bet)
                if new_status == 'Win':
                    # Basic payout is for $2. If bet_amount is different, scale it.
                    # Payout from Equibase is usually for a $2 wager.
                    ratio = float(bet['bet_amount']) / 2.0
                    payout = float(payout) * ratio
            
            # Update bet
            update_data = {
                'status': new_status,
                'payout': payout,
                'updated_at': datetime.now().isoformat()
            }
            
            supabase.table('hranalyzer_bets').update(update_data).eq('id', bet['id']).execute()
            resolved_count += 1
            updated_bets.append({
                'id': bet['id'], 
                'old_status': 'Pending', 
                'new_status': new_status,
                'payout': payout
            })
            
        return jsonify({
            'success': True,
            'resolved_count': resolved_count,
            'details': updated_bets
        })
        
    except Exception as e:
        traceback.print_exc()
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