"""
Flask Backend API for Horse Racing Analyzer
Provides endpoints for DRF PDF upload, race data retrieval, and Equibase crawling
"""

import os
import sys
print("Backend script starting...", file=sys.stdout, flush=True)
import subprocess
from datetime import date, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from supabase_client import get_supabase_client
from bet_resolution import resolve_all_pending_bets
import traceback
import pytz

try:
    print("Initializing Flask app...", file=sys.stdout, flush=True)
    app = Flask(__name__)
    CORS(app)
    print(f"Flask app created: {app}", file=sys.stdout, flush=True)
except Exception as e:
    print(f"CRITICAL ERROR creating Flask app: {e}", file=sys.stdout, flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)

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
            'database': 'connected',
            'version': '1.0.2'
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/crawl-changes', methods=['POST'])
def trigger_crawl_changes():
    """
    Trigger the late changes crawler to fetch scratches, jockey changes, etc.
    Can be called via: curl -X POST http://localhost:5001/api/crawl-changes
    """
    try:
        from crawl_scratches import crawl_late_changes
        
        reset_param = request.args.get('reset') or request.json.get('reset')
        should_reset = str(reset_param).lower() == 'true'
        
        count = crawl_late_changes(reset_first=should_reset)
        
        return jsonify({
            'success': True,
            'message': f'Crawled changes successfully (Reset={should_reset})',
            'changes_processed': count
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
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
            .select('race_id, id, program_number, finish_position, hranalyzer_horses(horse_name), hranalyzer_trainers(trainer_name)')\
            .in_('race_id', race_ids)\
            .execute()
            
        all_entries = entries_response.data

        # 2.5 Get Claims for these races
        claims_response = supabase.table('hranalyzer_claims')\
            .select('race_id')\
            .in_('race_id', race_ids)\
            .execute()
        
        races_with_claims = set(c['race_id'] for c in claims_response.data)

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
                horse_name = (entry.get('hranalyzer_horses') or {}).get('horse_name', 'Unknown')
                trainer_name = (entry.get('hranalyzer_trainers') or {}).get('trainer_name', 'N/A')
                race_stats[rid]['results'].append({
                    'position': entry['finish_position'],
                    'horse': horse_name,
                    'number': entry.get('program_number'),
                    'trainer': trainer_name
                })

        # Sort results by position for each race
        for rid in race_stats:
            race_stats[rid]['results'].sort(key=lambda x: x['position'])

        races = []
        for race in raw_races:
            track_name = (race.get('hranalyzer_tracks') or {}).get('track_name', race['track_code'])
            
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

            # Auto-correct status if results exist
            current_status = race['race_status']
            if len(stats['results']) > 0:
                current_status = 'completed'

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
                'race_status': current_status,
                'has_claims': race['id'] in races_with_claims,
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
            name = (r.get('hranalyzer_tracks') or {}).get('track_name', code)
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
        
        # Get current time for comparison
        now_utc = datetime.now(pytz.utc)
        
        for r in today_response.data:
            name = (r.get('hranalyzer_tracks') or {}).get('track_name', r['track_code'])
            
            # Auto-correct status if results exist
            entries = r.get('hranalyzer_race_entries') or []
            has_results = any(e.get('finish_position') in [1, 2, 3] for e in entries)
            race_status = r['race_status']
            if has_results:
                race_status = 'completed'

            if name not in summary_map:
                summary_map[name] = {
                    'track_name': name,
                    'track_code': r['track_code'],
                    'total': 0,
                    'upcoming': 0,
                    'completed': 0,
                    'cancelled': 0,
                    'is_fully_cancelled': False,
                    'next_race_time': None,
                    'next_race_iso': None,
                    'last_race_winner': None,
                    'last_race_number': 0
                }
            
            summary_map[name]['total'] += 1
            
            if race_status == 'completed':
                summary_map[name]['completed'] += 1
                # Update last race winner (assuming races ordered by race_number)
                if r['race_number'] > summary_map[name]['last_race_number']:
                    summary_map[name]['last_race_number'] = r['race_number']
                    # Find winner
                    winner_entry = next((e for e in r.get('hranalyzer_race_entries', []) if e['finish_position'] == 1), None)
                    if winner_entry and winner_entry.get('hranalyzer_horses'):
                        summary_map[name]['last_race_winner'] = winner_entry['hranalyzer_horses']['horse_name']
                    else:
                        summary_map[name]['last_race_winner'] = "Unknown"
            elif race_status == 'cancelled':
                summary_map[name]['cancelled'] += 1
            else:
                summary_map[name]['upcoming'] += 1
                
                # Update next race time (Find the FIRST upcoming race that is in the future)
                # SKIP if it is cancelled! (Logic already in elif above but being safe)
                if race_status != 'cancelled':
                    if True: # Always try to parse time for better data
                        post_time_str = r.get('post_time')
                    if post_time_str:
                         try:
                             # Clean "Post Time" text if present
                             clean_time_str = post_time_str.replace("Post Time", "").replace("Post time", "").strip()
                             clean_time_str = clean_time_str.replace("ET", "").replace("PT", "").replace("CT", "").replace("MT", "").strip()
                             
                             # Parse TIME
                             pt = None
                             for fmt in ["%I:%M %p", "%H:%M", "%H:%M:%S", "%I:%M%p"]:
                                 try:
                                     pt = datetime.strptime(clean_time_str, fmt).time()
                                     break
                                 except ValueError:
                                     continue
                             
                             if pt:
                                 today_dt = datetime.strptime(today, "%Y-%m-%d").date()
                                 dt = datetime.combine(today_dt, pt)
                                 
                                 tz_name = r.get('hranalyzer_tracks', {}).get('timezone', 'America/New_York')
                                 if not tz_name: tz_name = 'America/New_York'
                                 
                                 local_tz = pytz.timezone(tz_name)
                                 localized = local_tz.localize(dt)
                                 
                                 # Logic: We want the EARLIEST upcoming race
                                 # Since the loop is ordered by race_number, we usually just take the first one we find
                                 # However, if we already have a next_race_iso, check if this one is earlier?
                                 # Actually, the user wants the "Next Post".
                                 # If we have multiple upcoming races, which one is "Next"? The one with the lowest race number usually.
                                 # But if Race 1 is technically "upcoming" (not resulted) but time is 1 PM and now it is 5 PM,
                                 # showing Race 1 as "Next Post" with "Post Time" (past) is correct data-wise (it IS the next unresolved race).
                                 # The crawler needs to fix the status. Ideally backend shows "Next *Scheduled* Post".
                                 
                                 if summary_map[name]['next_race_iso'] is None:
                                     summary_map[name]['next_race_iso'] = localized.isoformat()
                                     summary_map[name]['next_race_time'] = localized.strftime("%I:%M %p").lstrip('0')
                                     summary_map[name]['timezone'] = tz_name
                                 
                         except Exception as e:
                             # print(f"Error parsing time {post_time_str}: {e}")
                             if not summary_map[name]['next_race_time']:
                                 summary_map[name]['next_race_time'] = post_time_str


        # Final pass for fully cancelled tracks
        for name in summary_map:
            if summary_map[name]['total'] > 0 and summary_map[name]['cancelled'] == summary_map[name]['total']:
                summary_map[name]['is_fully_cancelled'] = True

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
                results:hranalyzer_race_entries(finish_position, program_number, horse:hranalyzer_horses(horse_name), trainer:hranalyzer_trainers(trainer_name)),
                claims:hranalyzer_claims(id),
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
            
            # Formatted results Top 3
            formatted_results = []
            winner_name = 'N/A'
            
            # Prefer explicit column if populated (from backfill/crawler)
            winner_program_number = race.get('winner_program_number')
            
            # Fallback calculation if column is null
            calculated_winner_pgm = None
            
            for r in results_data:
                pos = r.get('finish_position')
                if pos and pos in [1, 2, 3]:
                    horse_name = (r.get('horse') or {}).get('horse_name', 'Unknown')
                    trainer_name = (r.get('trainer') or {}).get('trainer_name', 'N/A')
                    formatted_results.append({
                        'position': pos,
                        'horse': horse_name,
                        'number': r.get('program_number'),
                        'trainer': trainer_name
                    })
                    if pos == 1:
                        winner_name = horse_name
                        calculated_winner_pgm = r.get('program_number')
            
            # Use calculated if explicit is missing
            if not winner_program_number:
                winner_program_number = calculated_winner_pgm
            
            formatted_results.sort(key=lambda x: x['position'])

            races.append({
                'race_key': race['race_key'],
                'track_code': race['track_code'],
                'track_name': (race.get('track') or {}).get('track_name', race['track_code']),
                'race_number': race['race_number'],
                'race_date': race['race_date'],
                'post_time': race['post_time'],
                'race_type': race['race_type'],
                'surface': race['surface'],
                'distance': race['distance'],
                'purse': race['purse'],
                'entry_count': len(race.get('all_entries', [])),
                'race_status': race['race_status'],
                'has_claims': len(race.get('claims', [])) > 0,
                'data_source': race['data_source'],
                'id': race['id'],
                'winner': winner_name,
                'winner_program_number': winner_program_number,
                'results': formatted_results, # Top 3
                'time': race.get('final_time') or 'N/A',
                'link': race.get('equibase_chart_url', '#')
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



        # Add navigation logic (Next/Prev Race)
        # Find sibling races (same track, same date)
        # Robustness: Strip whitespace and ensure string format
        track_c = str(race.get('track_code', '')).strip()
        race_d = str(race.get('race_date', ''))
        
        siblings_response = supabase.table('hranalyzer_races')\
            .select('race_key, race_number')\
            .eq('track_code', track_c)\
            .eq('race_date', race_d)\
            .order('race_number')\
            .execute()
            
        siblings = siblings_response.data
        if siblings:
            # Find current index
            current_idx = next((i for i, r in enumerate(siblings) if r['race_key'] == race['race_key']), -1)
            
            nav_data = {
                'prev_race_key': None,
                'next_race_key': None
            }
            
            if current_idx > 0:
                nav_data['prev_race_key'] = siblings[current_idx - 1]['race_key']
            
            if current_idx < len(siblings) - 1:
                nav_data['next_race_key'] = siblings[current_idx + 1]['race_key']
                
            # Update the response JSON (dirty but effective patch without rewriting the whole dict above)
            # Actually, let's just create the dict properly.
                
            # Auto-correct status if results exist (User reported false CANCELLED status on races with winners)
            has_results = any(e.get('finish_position') in [1, 2, 3] for e in entries)
            current_status = race['race_status']
            if has_results:
                current_status = 'completed'

            return jsonify({
                'race': {
                     'race_key': race['race_key'],
                    'track_code': race['track_code'],
                    'track_name': (race.get('hranalyzer_tracks') or {}).get('track_name', race['track_code']),
                    'location': (race.get('hranalyzer_tracks') or {}).get('location'),
                    'race_number': race['race_number'],
                    'race_date': race['race_date'],
                    'post_time': race['post_time'],
                    'race_type': race['race_type'],
                    'surface': race['surface'],
                    'distance': race['distance'],
                    'distance_feet': race['distance_feet'],
                    'conditions': race['conditions'],
                    'purse': race['purse'],
                    'race_status': current_status,
                    'data_source': race['data_source'],
                    'final_time': race['final_time'],
                    'fractional_times': race['fractional_times'],
                    'equibase_chart_url': race['equibase_chart_url'],
                    'equibase_pdf_url': race['equibase_pdf_url']
                },
                'entries': entries,
                'exotic_payouts': exotic_payouts,
                'claims': claims,
                'navigation': nav_data
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
                'program_number': item.get('program_number'),
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


@app.route('/api/changes', methods=['GET'])
def get_changes():
    """
    Get all race changes (scratches, jockey changes, etc.)
    Query params:
    - view: 'upcoming' (default) or 'all'
    - mode: 'upcoming' (default) or 'history'
    - page: Page number (default 1)
    - limit: Results per page (default 20)
    - track: Filter by track code (e.g., 'SA', 'DMR')
    
    This endpoint merges data from:
    1. hranalyzer_race_entries (existing scratches with scratched=True)
    2. hranalyzer_changes (new changes table for jockey changes, etc.)
    """
    try:
        # Get query parameters
        view_mode = request.args.get('mode', 'upcoming') # 'upcoming' or 'history'
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        track_filter = request.args.get('track', 'All') # New track filter
        
        start = (page - 1) * limit
        end = start + limit
        
        today = date.today().isoformat()
        
        supabase = get_supabase_client()
        
        all_changes = []
        
        # =======================================================================
        # DEDUPLICATION FIX: Fetch detailed changes FIRST (Source 2), then
        # skip generic entries from Source 1 if a detailed scratch exists.
        # =======================================================================
        
        # Set to track entry_ids that have detailed scratch records
        entries_with_detailed_scratches = set()
        
        # --- SOURCE 2 (FIRST): Detailed Changes from hranalyzer_changes table ---
        try:
            changes_query = supabase.table('hranalyzer_changes')\
                .select('''
                    id,
                    entry_id,
                    change_type,
                    description,
                    created_at,
                    entry:hranalyzer_race_entries(
                        id,
                        program_number,
                        horse:hranalyzer_horses(horse_name)
                    ),
                    race:hranalyzer_races!inner(
                        id,
                        track_code, 
                        race_date, 
                        race_number,
                        post_time
                    )
                ''')
                
            if view_mode == 'upcoming':
                changes_query = changes_query.eq('race.race_date', today)
            else:
                changes_query = changes_query.lt('race.race_date', today)

            # Apply Track Filter
            if track_filter != 'All':
                changes_query = changes_query.eq('race.track_code', track_filter)

            changes_response = changes_query.execute()
            
            for item in changes_response.data or []:
                race = item.get('race') or {}
                entry = item.get('entry') or {}
                horse = entry.get('horse') or {}
                
                # Track entry_ids that have detailed scratch records
                if item.get('change_type') == 'Scratch' and item.get('entry_id'):
                    entries_with_detailed_scratches.add(item['entry_id'])
                
                all_changes.append({
                    'id': item['id'],
                    'race_id': race.get('id'),
                    'race_date': str(race.get('race_date')),
                    'track_code': race.get('track_code'),
                    'race_number': race.get('race_number'),
                    'post_time': race.get('post_time', 'N/A'),
                    'program_number': entry.get('program_number', '-'),
                    'horse_name': horse.get('horse_name', 'Race-wide'),
                    'change_type': item['change_type'],
                    'description': item['description'],
                    'change_time': item.get('created_at'),
                    '_source': 'changes'
                })

        except Exception as e:
            # hranalyzer_changes table might not exist yet, that's OK
            print(f"DEBUG: Error fetching hranalyzer_changes: {e}")
            pass
        
        # --- SOURCE 1 (SECOND): Generic Scratches from hranalyzer_race_entries ---
        # ONLY add entries that don't already have detailed scratch records
        scratch_query = supabase.table('hranalyzer_race_entries')\
            .select('''
                id,
                program_number,
                scratched,
                updated_at,
                horse:hranalyzer_horses(horse_name),
                race:hranalyzer_races!inner(
                    id, 
                    track_code, 
                    race_date, 
                    race_number,
                    post_time
                )
            ''')\
            .eq('scratched', True)
            
        if view_mode == 'upcoming':
            scratch_query = scratch_query.eq('race.race_date', today)
        else:
            scratch_query = scratch_query.lt('race.race_date', today)
            
        # Apply Track Filter
        if track_filter != 'All':
            scratch_query = scratch_query.eq('race.track_code', track_filter)
            
        scratch_response = scratch_query.execute()
        
        for item in scratch_response.data or []:
            entry_id = item['id']
            
            # SKIP if this entry already has a detailed scratch in hranalyzer_changes
            if entry_id in entries_with_detailed_scratches:
                continue
                
            race = item.get('race') or {}
            horse = item.get('horse') or {}
            
            # Construct a standardized change object
            change = {
                'id': entry_id,
                'race_id': race.get('id'),
                'track_code': race.get('track_code'),
                'race_date': str(race.get('race_date')),
                'race_number': race.get('race_number'),
                'program_number': item.get('program_number'),
                'horse_name': horse.get('horse_name'),
                'change_type': 'Scratch',
                'description': 'Scratched',
                'change_time': item.get('updated_at'),
                'post_time': race.get('post_time'),
                '_source': 'entries'
            }
            all_changes.append(change)
        
        # ---------------------------------------------------------------------
        # BROAD NORMALIZATION & PRIORITY SELECTION
        # ---------------------------------------------------------------------
        
        def get_type_class(item):
            t = (item.get('change_type') or "").lower()
            desc = (item.get('description') or "").lower()
            
            # Helper: Is this effectively a scratch?
            is_scratch_related = 'scratch' in t or ('scratch' in desc and 'reason' in desc)
            
            if is_scratch_related: return 'scratch'
            if 'jockey' in t: return 'jockey'
            if 'weight' in t: return 'weight'
            if 'cancelled' in t: return 'cancelled'
            return 'other'

        def normalize_identity(item):
            # Extract and clean PGM
            pgm = str(item.get('program_number') or "").strip().upper().lstrip('0')
            if pgm in ["-", "NONE", "NULL"]: pgm = ""
            
            # Extract and clean Horse Name
            h_name = str(item.get('horse_name') or "").strip().lower()
            if h_name in ["", "race-wide", "unknown", "none", "null"]:
                h_name = "RACE_WIDE"
                
            # Identity Anchor: PGM is king if it looks like a number/code, else Horse Name
            if pgm:
                return f"PGM_{pgm}"
            return h_name

        # Normalization Step
        normalized_map = {} # (track, date, race, identity, type_class) -> [candidates]
        
        for item in all_changes:
            track = str(item.get('track_code') or "").strip().upper()
            r_date = str(item.get('race_date') or "").strip()[:10] # YYYY-MM-DD
            r_num = str(item.get('race_number') or "").strip()
            
            identity = normalize_identity(item)
            t_class = get_type_class(item)
            
            # Grouping key for logical events
            # For Race-wide messages, we include a slice of description to keep different ones separate
            if identity == "RACE_WIDE":
                desc_slug = (item.get('description') or "").strip()[:30].lower()
                event_key = (track, r_date, r_num, identity, t_class, desc_slug)
            else:
                event_key = (track, r_date, r_num, identity, t_class)
            
            if event_key not in normalized_map:
                normalized_map[event_key] = []
            normalized_map[event_key].append(item)

        final_list = []
        
        for event_key, candidates in normalized_map.items():
            if not candidates: continue
            
            if len(candidates) == 1:
                # If single candidate is effectively a scratch but labeled "Other", fix it for UI
                c = candidates[0]
                if get_type_class(c) == 'scratch' and c.get('change_type') == 'Other':
                     c['change_type'] = 'Scratch'
                final_list.append(c)
                continue
                
            # Final Selection Strategy: LATEST TIME WINS
            # User wants the most recently created entry to be the source of truth.
            def final_ranking(c):
                # Parse timestamp
                ts = c.get('change_time')
                if not ts:
                    return "" # Low priority
                return str(ts)
            
            # Sort by time descending (latest first)
            candidates.sort(key=final_ranking, reverse=True)
            
            # Select the winner (latest)
            winner = candidates[0]
            
            # If the winner is a scratch-related update (e.g. "Other" reason change),
            # ensure it displays as a standardized "Scratch" alert in the UI.
            if get_type_class(winner) == 'scratch' and winner.get('change_type') == 'Other':
                winner['change_type'] = 'Scratch'
                
            final_list.append(winner)

        # --- FILTER: Only horse-specific changes (exclude Race-wide) unless it's a legitimate cancellation ---
        # Also EXCLUDE 'Wagering' type or generic wagering text to prevent "plaguing" the user
        final_list = [
            c for c in final_list 
            if c.get('horse_name') not in (None, '', 'Race-wide', 'Race-Wide') 
            or c.get('change_type') == 'Race Cancelled'
        ]
        
        # Strict Wagering Filter
        final_list = [
            c for c in final_list
            if c.get('change_type') != 'Wagering'
            and 'wagering' not in (c.get('description') or '').lower()
        ]

        # --- FINAL SORTING ---
        if view_mode == 'upcoming':
            final_list.sort(key=lambda x: (
                str(x.get('race_date') or ''),
                str(x.get('track_code') or ''),
                int(str(x.get('race_number') or 0)),
                normalize_identity(x)
            ))
        else:
            final_list.sort(key=lambda x: (
                str(x.get('race_date') or ''),
                str(x.get('track_code') or ''),
                int(str(x.get('race_number') or 0)),
                normalize_identity(x)
            ), reverse=True)
        
        # --- Pagination ---
        total_count = len(final_list)
        # Fix: end is start + limit, so [start:end] gives exactly 'limit' results.
        paginated_changes = final_list[start:end]

        
        for c in paginated_changes:
            c.pop('_source', None)
            
        return jsonify({
            'changes': paginated_changes,
            'count': total_count,
            'page': page,
            'limit': limit,
            'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/race/<race_id>/changes', methods=['GET'])
def get_race_changes(race_id):
    """
    Get changes for a specific race.
    Returns scratches from race_entries + changes from hranalyzer_changes table.
    """
    try:
        supabase = get_supabase_client()
        
        all_changes = []
        
        # SOURCE 1: Scratches from race_entries
        scratch_response = supabase.table('hranalyzer_race_entries')\
            .select('''
                id, program_number, scratched, updated_at,
                horse:hranalyzer_horses(horse_name)
            ''')\
            .eq('race_id', race_id)\
            .eq('scratched', True)\
            .execute()
        
        for item in scratch_response.data or []:
            horse = item.get('horse') or {}
            all_changes.append({
                'id': item['id'],
                'program_number': item.get('program_number', '-'),
                'horse_name': horse.get('horse_name', 'Unknown'),
                'change_type': 'Scratch',
                'description': 'Scratched',
                'change_time': item.get('updated_at')
            })
        
        # SOURCE 2: Changes from hranalyzer_changes table
        try:
            changes_response = supabase.table('hranalyzer_changes')\
                .select('''
                    id, change_type, description, change_time,
                    entry:hranalyzer_race_entries(
                        program_number,
                        horse:hranalyzer_horses(horse_name)
                    )
                ''')\
                .eq('race_id', race_id)\
                .execute()
            
            for item in changes_response.data or []:
                entry = item.get('entry') or {}
                horse = entry.get('horse') or {}
                
                all_changes.append({
                    'id': item['id'],
                    'program_number': entry.get('program_number', '-'),
                    'horse_name': horse.get('horse_name', 'Race-wide'),
                    'change_type': item['change_type'],
                    'description': item['description'],
                    'change_time': item['change_time']
                })
        except:
            pass  # Table might not exist
        
        return jsonify({
            'changes': all_changes,
            'count': len(all_changes)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/scratches', methods=['GET'])
def get_scratches():
    """
    Get all scratches suitable for display
    Query params:
    - view: 'upcoming' (default) or 'all'
    - page: Page number (default 1)
    - limit: Results per page (default 20)
    """
    try:
        supabase = get_supabase_client()
        view_mode = request.args.get('view', 'upcoming')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        today = date.today().isoformat()
        
        # Calculate offset
        start = (page - 1) * limit
        end = start + limit - 1
        
        # Base query for scratches
        # We need count='exact' to get total distinct count
        query = supabase.table('hranalyzer_race_entries')\
            .select('''
                id, program_number, scratched, updated_at,
                horse:hranalyzer_horses(horse_name),
                trainer:hranalyzer_trainers(trainer_name),
                race:hranalyzer_races!inner(
                    id, track_code, race_date, race_number, post_time, race_status,
                    track:hranalyzer_tracks(track_name)
                )
            ''', count='exact')\
            .eq('scratched', True)
            
        # Filter and Sort
        if view_mode == 'upcoming':
             # Upcoming: Soonest first (ASC), then Track, then Race
             query = query.gte('race.race_date', today)\
                .order('race_date', foreign_table='race')\
                .order('track_code', foreign_table='race')\
                .order('race_number', foreign_table='race')\
                .order('id')
        else:
             # All History: Most recent first (DESC), then Track, then Race, then ID
             query = query.lte('race.race_date', today)\
                .order('race_date', desc=True, foreign_table='race')\
                .order('track_code', foreign_table='race')\
                .order('race_number', foreign_table='race')\
                .order('id')
             
        # Apply pagination
        response = query.range(start, end).execute()
        
        count = response.count if response.count is not None else 0
        data = response.data
        
        scratches = []
        for item in data:
            # Safe access
            race = item.get('race') or {}
            track = race.get('track') or {}
            horse = item.get('horse') or {}
            trainer = item.get('trainer') or {}
            
            # Calculate time safely
            formatted_time = "N/A"
            if race.get('post_time'):
                 formatted_time = race['post_time']
            
            scratches.append({
                'id': item['id'],
                'race_date': race.get('race_date'),
                'track_code': race.get('track_code'),
                'track_name': track.get('track_name', race.get('track_code')),
                'race_number': race.get('race_number'),
                'post_time': formatted_time,
                'program_number': item['program_number'],
                'horse_name': horse.get('horse_name', 'Unknown'),
                'trainer_name': trainer.get('trainer_name', 'Unknown'),
                'status': 'Scratched'
            })
            
        return jsonify({
            'scratches': scratches,
            'count': count,
            'page': page,
            'limit': limit,
            'total_pages': (count + limit - 1) // limit if limit > 0 else 1
        })
            
        # Sort by Date (desc), Track, Race
        scratches.sort(key=lambda x: (x['race_date'], x['track_code'], x['race_number']), reverse=True)
        
        return jsonify({
            'scratches': scratches,
            'count': len(scratches)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==============================================
# WALLET ENDPOINTS
# ==============================================

@app.route('/api/wallet', methods=['GET'])
def get_wallet():
    """Get current wallet balance"""
    try:
        supabase = get_supabase_client()
        # Default user for single player
        user_ref = 'default_user'
        
        # Get or Create
        res = supabase.table('hranalyzer_wallets').select('*').eq('user_ref', user_ref).execute()
        
        if not res.data:
            # Auto-create if missing (and if SQL table exists)
            try:
                # Attempt insert
                init_data = {'user_ref': user_ref, 'balance': 1000.00}
                res = supabase.table('hranalyzer_wallets').insert(init_data).execute()
            except Exception as e:
                # If table missing or error
                print(f"Error creating wallet: {e}")
                return jsonify({'balance': 1000.00, 'is_mock': True})
        
        wallet = res.data[0]
        return jsonify({
            'balance': float(wallet['balance']),
            'currency': 'USD'
        })
    except Exception as e:
        traceback.print_exc()
        # Fallback for resiliency
        return jsonify({'balance': 1000.00, 'error': str(e)}), 500


@app.route('/api/wallet/transaction', methods=['POST'])
def wallet_transaction():
    """
    Manually add or burn funds
    Body: { "type": "deposit"|"withdraw", "amount": 100.0 }
    """
    try:
        supabase = get_supabase_client()
        data = request.get_json()
        trans_type = data.get('type')
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400

        user_ref = 'default_user'
        
        # Get current wallet
        res = supabase.table('hranalyzer_wallets').select('*').eq('user_ref', user_ref).single().execute()
        if not res.data:
            return jsonify({'error': 'Wallet not found'}), 404
        
        wallet = res.data
        current_bal = float(wallet['balance'])
        new_bal = current_bal
        
        if trans_type == 'deposit':
            new_bal += amount
        elif trans_type == 'withdraw':
            if current_bal < amount:
                return jsonify({'error': 'Insufficient funds'}), 400
            new_bal -= amount
        else:
            return jsonify({'error': 'Invalid transaction type'}), 400
            
        # Update
        update_res = supabase.table('hranalyzer_wallets').update({'balance': new_bal}).eq('id', wallet['id']).execute()
        
        # Log Transaction
        try:
             supabase.table('hranalyzer_transactions').insert({
                 'wallet_id': wallet['id'],
                 'amount': amount if trans_type == 'deposit' else -amount,
                 'transaction_type': trans_type.capitalize(),
                 'description': f'Manual {trans_type}'
             }).execute()
        except Exception as e:
            print(f"Transaction log failed: {e}")

        return jsonify({
            'success': True,
            'balance': new_bal,
            'message': f'Successfully {trans_type}ed ${amount}'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets', methods=['POST'])
def place_bet():
    """Place a new bet and deduct funds"""
    try:
        data = request.get_json()
        race_id = data.get('race_id')
        # Support both single horse and multi-horse selection
        horse_number = data.get('horse_number') # Single string or None
        horse_name = data.get('horse_name')     # Single string or None
        selection = data.get('selection')       # List of horse numbers for Box bets
        
        bet_type = data.get('bet_type', 'Win')
        amount = float(data.get('amount', 2.00)) # Base Unit Amount
        
        # Calculate Cost
        cost = amount
        if bet_type in ['Exacta Box', 'Trifecta Box'] and selection:
            import math
            n = len(selection)
            if bet_type == 'Exacta Box':
                # P(n, 2) = n * (n-1)
                count = n * (n - 1)
            elif bet_type == 'Trifecta Box':
                 # P(n, 3) = n * (n-1) * (n-2)
                count = n * (n - 1) * (n - 2)
            else:
                count = 1
            cost = amount * count
        elif bet_type == 'WPS' or bet_type == 'Win Place Show':
            # WPS = Win + Place + Show (3 bets)
            cost = amount * 3.0
        elif bet_type == 'Win Place' or bet_type == 'Place Show':
            # 2 bets
            cost = amount * 2.0
        elif bet_type == 'Exacta' or bet_type == 'Trifecta':
            # Straight Exotics = 1 bet
            cost = amount * 1.0
        elif 'Key' in bet_type and selection:
            # Key/Wheel Logic
            # Selection is expected to be a list of lists: [[1], [2,3], [4,5]]
            # Cost = Number of valid combinations * amount
            
            # Helper to calculate combinations
            def count_combinations(current_depth, selected_so_far):
                if current_depth >= len(selection):
                    return 1
                
                count = 0
                # Candidates for this position
                candidates = selection[current_depth]
                if not isinstance(candidates, list):
                    candidates = [candidates] # Handle simple list case if malformed
                    
                for horse in candidates:
                    # Standard logic: A horse cannot be in multiple positions in one combination
                    if horse not in selected_so_far:
                        count += count_combinations(current_depth + 1, selected_so_far + [horse])
                return count

            if bet_type == 'Exacta Key':
                # Needs 2 positions
                if len(selection) >= 2:
                    count = count_combinations(0, [])
                else:
                    count = 0
            elif bet_type == 'Trifecta Key':
                # Needs 3 positions
                if len(selection) >= 3:
                    count = count_combinations(0, [])
                else:
                    count = 0
            cost = amount * count
            
        if not race_id or not bet_type:
            return jsonify({'error': 'Missing required fields'}), 400

        supabase = get_supabase_client()
        
        # Verify race exists
        race = supabase.table('hranalyzer_races').select('id, race_status').eq('id', race_id).single().execute()
        if not race.data:
            return jsonify({'error': 'Race not found'}), 404
            
        # ---------------------------------------------------------
        # WALLET DEDUCTION
        # ---------------------------------------------------------
        user_ref = 'default_user'
        wallet_res = supabase.table('hranalyzer_wallets').select('*').eq('user_ref', user_ref).single().execute()
        
        if not wallet_res.data:
            # Try create? Or Error
            # Let's auto-create for smoother UX if first time
             try:
                init_data = {'user_ref': user_ref, 'balance': 1000.00}
                item = supabase.table('hranalyzer_wallets').insert(init_data).execute()
                wallet = item.data[0]
             except:
                return jsonify({'error': 'Wallet not configured'}), 500
        else:
            wallet = wallet_res.data
            
        current_bal = float(wallet['balance'])
        
        if current_bal < cost:
            return jsonify({'error': f'Insufficient funds. Cost: ${cost:.2f}, Balance: ${current_bal:.2f}'}), 400
            
        # Deduct funds
        new_bal = current_bal - cost
        supabase.table('hranalyzer_wallets').update({'balance': new_bal}).eq('id', wallet['id']).execute()
        
        # ---------------------------------------------------------

        # Insert bet
        bet = {
            'race_id': race_id,
            'horse_number': horse_number,
            'horse_name': horse_name,
            'selection': selection,
            'bet_type': bet_type,
            'bet_amount': amount,
            'bet_cost': cost,
            'status': 'Pending'
        }
        
        response = supabase.table('hranalyzer_bets').insert(bet).execute()
        bet_data = response.data[0]
        
        # Log Transaction
        try:
             supabase.table('hranalyzer_transactions').insert({
                 'wallet_id': wallet['id'],
                 'amount': -cost,
                 'transaction_type': 'Bet',
                 'reference_id': bet_data['id'],
                 'description': f'Bet on Race'
             }).execute()
        except:
            pass
        
        return jsonify({
            'success': True,
            'bet': bet_data,
            'new_balance': new_bal
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


@app.route('/api/bets/<bet_id>', methods=['DELETE'])
def delete_bet(bet_id):
    """Delete a bet"""
    try:
        supabase = get_supabase_client()
        
        # Verify it exists
        # In a real app we might check user ownership
        
        response = supabase.table('hranalyzer_bets').delete().eq('id', bet_id).execute()
        
        if not response.data:
            return jsonify({'error': 'Bet not found or already deleted'}), 404
            
        return jsonify({
            'success': True,
            'message': 'Bet deleted',
            'deleted_bet': response.data[0]
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets', methods=['DELETE'])
def delete_all_bets():
    """Delete ALL bets (Reset Stats)"""
    try:
        supabase = get_supabase_client()
        
        # Delete all rows
        # Supabase delete without filters deletes all rows? carefully check metadata
        # Usually need a filter like .neq('id', 0) to be safe or allowed
        response = supabase.table('hranalyzer_bets').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        
        return jsonify({
            'success': True,
            'message': 'All bets deleted'
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bets/resolve', methods=['POST'])
def resolve_bets():
    """
    Check pending bets against completed races and resolve them.
    Supports Win, Place, Show, Exacta Box, Trifecta Box.
    """
    try:
        supabase = get_supabase_client()
        
        # Call shared logic
        result = resolve_all_pending_bets(supabase)
        
        return jsonify(result)
        
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


# ==============================================
# HORSES ENDPOINTS
# ==============================================

@app.route('/api/horses', methods=['GET'])
def get_horses():
    """
    Get list of horses with aggregate stats.
    Query params:
    - search: Filter by horse name (optional)
    - limit: Number of results (default 50)
    - page: Page number for pagination (default 1)
    - with_races: If 'true', only return horses that have race entries
    """
    try:
        supabase = get_supabase_client()
        import re
        
        search = request.args.get('search', '').strip()
        limit = int(request.args.get('limit', 50))
        page = int(request.args.get('page', 1))
        with_races = request.args.get('with_races', 'false').lower() == 'true'
        offset = (page - 1) * limit
        
        # Helper function to check if a horse name is valid
        def is_valid_horse_name(name):
            if not name or len(name) < 2:
                return False
            # Exclude names that start with $, are just numbers/punctuation, or look like money amounts
            if name.startswith('$') or name.startswith('-'):
                return False
            if re.match(r'^[\d\s\.\,\-\$]+$', name):
                return False
            # Exclude common garbage patterns
            if name in ['-', '--', 'N/A', 'Unknown', 'TBD']:
                return False
            return True
        
        # Build base query for horses
        # Filter out garbage names using pattern matching
        query = supabase.table('hranalyzer_horses').select('*', count='exact')
        
        # Exclude names starting with $ or that are too short
        query = query.not_.like('horse_name', '$%')
        query = query.neq('horse_name', '-')
        query = query.neq('horse_name', '--')
        query = query.neq('horse_name', 'N/A')
        
        if search:
            query = query.ilike('horse_name', f'%{search}%')
        
        query = query.order('horse_name').range(offset, offset + limit - 1)
        response = query.execute()
        
        # Additional Python-side filtering for names that slip through
        horses_data = [h for h in response.data if is_valid_horse_name(h.get('horse_name', ''))]
        total_count = response.count or 0
        
        # Now get race entries for these horses to compute stats
        horse_ids = [h['id'] for h in horses_data]
        
        stats_map = {}
        if horse_ids:
            entries_response = supabase.table('hranalyzer_race_entries')\
                .select('''
                    horse_id, finish_position, scratched,
                    race:hranalyzer_races(race_date, track_code, race_status)
                ''')\
                .in_('horse_id', horse_ids)\
                .execute()
            
            for entry in entries_response.data:
                hid = entry['horse_id']
                if hid not in stats_map:
                    stats_map[hid] = {
                        'total_races': 0,
                        'wins': 0,
                        'places': 0,
                        'shows': 0,
                        'last_race_date': None,
                        'last_track': None
                    }
                
                # Skip scratched entries
                if entry.get('scratched'):
                    continue
                
                race = entry.get('race') or {}
                # Only count completed races
                if race.get('race_status') != 'completed':
                    continue
                    
                stats_map[hid]['total_races'] += 1
                
                pos = entry.get('finish_position')
                if pos == 1:
                    stats_map[hid]['wins'] += 1
                elif pos == 2:
                    stats_map[hid]['places'] += 1
                elif pos == 3:
                    stats_map[hid]['shows'] += 1
                
                # Track last race
                race_date = race.get('race_date')
                if race_date:
                    if not stats_map[hid]['last_race_date'] or race_date > stats_map[hid]['last_race_date']:
                        stats_map[hid]['last_race_date'] = race_date
                        stats_map[hid]['last_track'] = race.get('track_code')
        
        # Build response
        horses = []
        for h in horses_data:
            stats = stats_map.get(h['id'], {
                'total_races': 0, 'wins': 0, 'places': 0, 'shows': 0,
                'last_race_date': None, 'last_track': None
            })
            
            total = stats['total_races']
            win_pct = round((stats['wins'] / total) * 100, 1) if total > 0 else 0
            
            horses.append({
                'id': h['id'],
                'name': h['horse_name'],
                'sire': h.get('sire'),
                'dam': h.get('dam'),
                'color': h.get('color'),
                'sex': h.get('sex'),
                'total_races': total,
                'wins': stats['wins'],
                'places': stats['places'],
                'shows': stats['shows'],
                'win_percentage': win_pct,
                'last_race_date': stats['last_race_date'],
                'last_track': stats['last_track']
            })
        
        return jsonify({
            'horses': horses,
            'count': len(horses),
            'total': total_count,
            'page': page,
            'limit': limit,
            'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/horse/<horse_id>', methods=['GET'])
def get_horse_profile(horse_id):
    """
    Get detailed profile for a specific horse including race history.
    """
    try:
        supabase = get_supabase_client()
        
        # Get horse info
        horse_response = supabase.table('hranalyzer_horses')\
            .select('*')\
            .eq('id', horse_id)\
            .single()\
            .execute()
        
        if not horse_response.data:
            return jsonify({'error': 'Horse not found'}), 404
        
        horse = horse_response.data
        
        # Get all race entries for this horse
        entries_response = supabase.table('hranalyzer_race_entries')\
            .select('''
                id, program_number, finish_position, final_odds, 
                win_payout, place_payout, show_payout, scratched, run_comments,
                race:hranalyzer_races(
                    race_key, race_date, race_number, track_code, 
                    race_type, surface, distance, purse, race_status,
                    track:hranalyzer_tracks(track_name)
                ),
                jockey:hranalyzer_jockeys(jockey_name),
                trainer:hranalyzer_trainers(trainer_name)
            ''')\
            .eq('horse_id', horse_id)\
            .order('id', desc=True)\
            .execute()
        
        # Process race history
        race_history = []
        stats = {'total': 0, 'wins': 0, 'places': 0, 'shows': 0, 'earnings': 0}
        
        for entry in entries_response.data:
            race = entry.get('race') or {}
            track = race.get('track') or {}
            jockey = entry.get('jockey') or {}
            trainer = entry.get('trainer') or {}
            
            race_entry = {
                'race_key': race.get('race_key'),
                'race_date': race.get('race_date'),
                'track_code': race.get('track_code'),
                'track_name': track.get('track_name', race.get('track_code')),
                'race_number': race.get('race_number'),
                'race_type': race.get('race_type'),
                'surface': race.get('surface'),
                'distance': race.get('distance'),
                'purse': race.get('purse'),
                'program_number': entry.get('program_number'),
                'finish_position': entry.get('finish_position'),
                'final_odds': entry.get('final_odds'),
                'jockey_name': jockey.get('jockey_name', 'N/A'),
                'trainer_name': trainer.get('trainer_name', 'N/A'),
                'run_comments': entry.get('run_comments'),
                'scratched': entry.get('scratched', False),
                'race_status': race.get('race_status')
            }
            race_history.append(race_entry)
            
            # Compute stats from completed races
            if race.get('race_status') == 'completed' and not entry.get('scratched'):
                stats['total'] += 1
                pos = entry.get('finish_position')
                if pos == 1:
                    stats['wins'] += 1
                    if entry.get('win_payout'):
                        stats['earnings'] += float(entry['win_payout'])
                elif pos == 2:
                    stats['places'] += 1
                    if entry.get('place_payout'):
                        stats['earnings'] += float(entry['place_payout'])
                elif pos == 3:
                    stats['shows'] += 1
                    if entry.get('show_payout'):
                        stats['earnings'] += float(entry['show_payout'])
        
        # Sort by race date descending
        race_history.sort(key=lambda x: (x.get('race_date') or '', x.get('race_number') or 0), reverse=True)
        
        stats['win_percentage'] = round((stats['wins'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
        
        return jsonify({
            'horse': {
                'id': horse['id'],
                'name': horse['horse_name'],
                'sire': horse.get('sire'),
                'dam': horse.get('dam'),
                'color': horse.get('color'),
                'sex': horse.get('sex'),
                'foaling_year': horse.get('foaling_year')
            },
            'stats': stats,
            'race_history': race_history
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Legacy endpoint for backwards compatibility (will be removed later)
@app.route('/api/race-data')
def get_race_data():
    """Legacy endpoint - redirects to /api/past-races"""
    return get_past_races()


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)