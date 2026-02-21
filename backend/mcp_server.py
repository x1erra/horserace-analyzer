"""
MCP Server for TrackData.live
Provides read-only tools for AI agents to query horse racing data.
Runs alongside the Flask backend on port 8001.
"""

import os
import sys
import re
from datetime import date
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from mcp.server.fastmcp import FastMCP

# Import the shared Supabase client
sys.path.insert(0, os.path.dirname(__file__))
from supabase_client import get_supabase_client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def format_to_12h(time_str):
    """Convert 24h time string (HH:MM:SS) to 12h format."""
    if not time_str:
        return "N/A"
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        suffix = "AM" if h < 12 else "PM"
        h = h % 12 or 12
        return f"{h}:{m:02d} {suffix}"
    except Exception:
        return time_str


# ---------------------------------------------------------------------------
# Create MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "TrackData",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=8001,
)


# ---------------------------------------------------------------------------
# Tool: get_tracks
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tracks() -> dict:
    """
    Get all available horse racing tracks.
    Returns a list of tracks with their code, name, and location.
    """
    supabase = get_supabase_client()
    response = supabase.table('hranalyzer_tracks') \
        .select('track_code, track_name, location, timezone') \
        .order('track_name') \
        .execute()

    return {
        "tracks": response.data,
        "count": len(response.data)
    }


# ---------------------------------------------------------------------------
# Tool: get_todays_races
# ---------------------------------------------------------------------------

@mcp.tool()
def get_todays_races(track: str = "", status: str = "All") -> dict:
    """
    Get all races scheduled for today.

    Args:
        track: Filter by track code (e.g., 'GP' for Gulfstream Park). Leave empty for all tracks.
        status: Filter by race status: 'Upcoming', 'Completed', or 'All' (default).

    Returns a list of today's races with race number, track, post time, race type,
    surface, distance, purse, entry count, status, and results for completed races.
    """
    supabase = get_supabase_client()
    today = date.today().isoformat()

    # Fetch races
    query = supabase.table('hranalyzer_races') \
        .select('*, hranalyzer_tracks(track_name, location)') \
        .eq('race_date', today) \
        .order('race_number')

    response = query.execute()
    raw_races = response.data

    if not raw_races:
        return {"races": [], "count": 0, "date": today}

    # Batch fetch entries
    race_ids = [r['id'] for r in raw_races]

    entries_response = supabase.table('hranalyzer_race_entries') \
        .select('race_id, program_number, finish_position, hranalyzer_horses(horse_name)') \
        .in_('race_id', race_ids) \
        .execute()

    # Build stats map
    race_stats = {}
    for entry in entries_response.data:
        rid = entry['race_id']
        if rid not in race_stats:
            race_stats[rid] = {'count': 0, 'results': []}
        race_stats[rid]['count'] += 1
        if entry.get('finish_position') in [1, 2, 3]:
            horse_name = (entry.get('hranalyzer_horses') or {}).get('horse_name', 'Unknown')
            race_stats[rid]['results'].append({
                'position': entry['finish_position'],
                'horse': horse_name,
                'number': entry.get('program_number'),
            })

    for rid in race_stats:
        race_stats[rid]['results'].sort(key=lambda x: x['position'])

    # Build output
    races = []
    for race in raw_races:
        track_name = (race.get('hranalyzer_tracks') or {}).get('track_name', race['track_code'])

        # Apply filters
        if track and track != 'All':
            if track_name != track and race['track_code'] != track:
                continue
        if status and status != 'All':
            if status == 'Upcoming' and race['race_status'] == 'completed':
                continue
            if status == 'Completed' and race['race_status'] != 'completed':
                continue

        stats = race_stats.get(race['id'], {'count': 0, 'results': []})
        current_status = race['race_status']
        if len(stats['results']) > 0:
            current_status = 'completed'

        races.append({
            'race_key': race['race_key'],
            'track_code': race['track_code'],
            'track_name': track_name,
            'race_number': race['race_number'],
            'race_date': race['race_date'],
            'post_time': format_to_12h(race['post_time']),
            'race_type': race['race_type'],
            'surface': race['surface'],
            'distance': race['distance'],
            'purse': race['purse'],
            'entry_count': stats['count'],
            'race_status': current_status,
            'results': stats['results'],
        })

    return {"races": races, "count": len(races), "date": today}


# ---------------------------------------------------------------------------
# Tool: get_past_races
# ---------------------------------------------------------------------------

@mcp.tool()
def get_past_races(
    track: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
) -> dict:
    """
    Get past race results with optional filters.

    Args:
        track: Filter by track code (e.g., 'GP'). Leave empty for all tracks.
        start_date: Only include races on or after this date (YYYY-MM-DD).
        end_date: Only include races on or before this date (YYYY-MM-DD).
        limit: Maximum number of races to return (default 50, max 200).

    Returns a list of completed races with winners, top-3 finishers, payouts, and times.
    """
    supabase = get_supabase_client()
    today = date.today().isoformat()
    limit = min(limit, 200)

    query = supabase.table('hranalyzer_races') \
        .select('''
            *,
            track:hranalyzer_tracks(track_name, location),
            results:hranalyzer_race_entries(finish_position, program_number, horse:hranalyzer_horses(horse_name))
        ''') \
        .lte('race_date', today) \
        .order('race_date', desc=True) \
        .order('race_number', desc=False) \
        .in_('race_status', ['completed', 'past_drf_only', 'cancelled'])

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

        formatted_results = []
        winner_name = 'N/A'
        for r in results_data:
            pos = r.get('finish_position')
            if pos and pos in [1, 2, 3]:
                horse_name = (r.get('horse') or {}).get('horse_name', 'Unknown')
                formatted_results.append({
                    'position': pos,
                    'horse': horse_name,
                    'number': r.get('program_number'),
                })
                if pos == 1:
                    winner_name = horse_name
        formatted_results.sort(key=lambda x: x['position'])

        races.append({
            'race_key': race['race_key'],
            'track_code': race['track_code'],
            'track_name': (race.get('track') or {}).get('track_name', race['track_code']),
            'race_number': race['race_number'],
            'race_date': race['race_date'],
            'post_time': format_to_12h(race.get('post_time')),
            'race_type': race.get('race_type'),
            'surface': race.get('surface'),
            'distance': race.get('distance'),
            'purse': race.get('purse'),
            'race_status': race['race_status'],
            'winner': winner_name,
            'results': formatted_results,
            'time': race.get('final_time') or 'N/A',
        })

    return {"races": races, "count": len(races)}


# ---------------------------------------------------------------------------
# Tool: get_race_details
# ---------------------------------------------------------------------------

@mcp.tool()
def get_race_details(race_key: str) -> dict:
    """
    Get full details for a specific race, including all entries with horses,
    jockeys, trainers, odds, finish positions, and payouts.

    Args:
        race_key: The race key in format TRACK-YYYYMMDD-RACENUM (e.g., 'GP-20260221-3').

    Returns complete race card with all entries and results.
    """
    supabase = get_supabase_client()

    # Get race
    race_response = supabase.table('hranalyzer_races') \
        .select('*, hranalyzer_tracks(track_name, location)') \
        .eq('race_key', race_key) \
        .execute()

    if not race_response.data:
        return {"error": f"Race not found: {race_key}"}

    race = race_response.data[0]

    # Get entries
    entries_response = supabase.table('hranalyzer_race_entries') \
        .select('''
            id, program_number, post_position, morning_line_odds,
            finish_position, official_position, final_odds,
            win_payout, place_payout, show_payout,
            scratched, run_comments, weight,
            horse:hranalyzer_horses(horse_name),
            jockey:hranalyzer_jockeys(jockey_name),
            trainer:hranalyzer_trainers(trainer_name),
            owner:hranalyzer_owners(owner_name)
        ''') \
        .eq('race_id', race['id']) \
        .order('program_number') \
        .execute()

    entries = []
    for entry in entries_response.data:
        entries.append({
            'program_number': entry.get('program_number'),
            'post_position': entry.get('post_position'),
            'horse_name': (entry.get('horse') or {}).get('horse_name', 'Unknown'),
            'jockey_name': (entry.get('jockey') or {}).get('jockey_name', 'N/A'),
            'trainer_name': (entry.get('trainer') or {}).get('trainer_name', 'N/A'),
            'owner_name': (entry.get('owner') or {}).get('owner_name', 'N/A'),
            'morning_line_odds': entry.get('morning_line_odds'),
            'final_odds': entry.get('final_odds'),
            'weight': entry.get('weight'),
            'finish_position': entry.get('finish_position'),
            'official_position': entry.get('official_position'),
            'win_payout': entry.get('win_payout'),
            'place_payout': entry.get('place_payout'),
            'show_payout': entry.get('show_payout'),
            'scratched': entry.get('scratched', False),
            'run_comments': entry.get('run_comments'),
        })

    # Get exotic payouts
    exotics_response = supabase.table('hranalyzer_exotic_payouts') \
        .select('wager_type, winning_combination, base_bet, payout') \
        .eq('race_id', race['id']) \
        .execute()

    # Get claims
    claims_response = supabase.table('hranalyzer_claims') \
        .select('horse_name, program_number, new_trainer_name, new_owner_name, claim_price') \
        .eq('race_id', race['id']) \
        .execute()

    track_info = race.get('hranalyzer_tracks') or {}

    return {
        "race": {
            'race_key': race['race_key'],
            'track_code': race['track_code'],
            'track_name': track_info.get('track_name', race['track_code']),
            'race_number': race['race_number'],
            'race_date': race['race_date'],
            'post_time': format_to_12h(race.get('post_time')),
            'race_type': race.get('race_type'),
            'surface': race.get('surface'),
            'distance': race.get('distance'),
            'purse': race.get('purse'),
            'conditions': race.get('conditions'),
            'race_status': race['race_status'],
            'final_time': race.get('final_time'),
        },
        "entries": entries,
        "exotic_payouts": exotics_response.data,
        "claims": claims_response.data,
        "entry_count": len(entries),
    }


# ---------------------------------------------------------------------------
# Tool: get_horses
# ---------------------------------------------------------------------------

@mcp.tool()
def get_horses(search: str = "", limit: int = 50, page: int = 1) -> dict:
    """
    Search for horses by name and get their stats.

    Args:
        search: Horse name to search for (partial match, case-insensitive).
        limit: Number of results per page (default 50, max 100).
        page: Page number (default 1).

    Returns a list of horses with win/place/show stats and winning percentage.
    """
    supabase = get_supabase_client()
    limit = min(limit, 100)
    offset = (page - 1) * limit

    def is_valid_horse_name(name):
        if not name or len(name) < 2:
            return False
        if name.startswith('$') or name.startswith('-'):
            return False
        if re.match(r'^[\d\s\.\,\-\$]+$', name):
            return False
        if name in ['-', '--', 'N/A', 'Unknown', 'TBD']:
            return False
        return True

    query = supabase.table('hranalyzer_horses').select('*', count='exact')
    query = query.not_.like('horse_name', '$%')
    query = query.neq('horse_name', '-')
    query = query.neq('horse_name', '--')
    query = query.neq('horse_name', 'N/A')

    if search:
        query = query.ilike('horse_name', f'%{search}%')

    query = query.order('horse_name').range(offset, offset + limit - 1)
    response = query.execute()

    horses_data = [h for h in response.data if is_valid_horse_name(h.get('horse_name', ''))]
    total_count = response.count or 0

    # Get stats
    horse_ids = [h['id'] for h in horses_data]
    stats_map = {}
    if horse_ids:
        entries_response = supabase.table('hranalyzer_race_entries') \
            .select('horse_id, finish_position, scratched, race:hranalyzer_races(race_date, track_code, race_status)') \
            .in_('horse_id', horse_ids) \
            .execute()

        for entry in entries_response.data:
            hid = entry['horse_id']
            if hid not in stats_map:
                stats_map[hid] = {'total_races': 0, 'wins': 0, 'places': 0, 'shows': 0}
            if entry.get('scratched'):
                continue
            race = entry.get('race') or {}
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

    horses = []
    for h in horses_data:
        stats = stats_map.get(h['id'], {'total_races': 0, 'wins': 0, 'places': 0, 'shows': 0})
        total = stats['total_races']
        win_pct = round((stats['wins'] / total) * 100, 1) if total > 0 else 0
        horses.append({
            'id': h['id'],
            'name': h['horse_name'],
            'sire': h.get('sire'),
            'dam': h.get('dam'),
            'sex': h.get('sex'),
            'total_races': total,
            'wins': stats['wins'],
            'places': stats['places'],
            'shows': stats['shows'],
            'win_percentage': win_pct,
        })

    return {
        "horses": horses,
        "count": len(horses),
        "total": total_count,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# Tool: get_horse_profile
# ---------------------------------------------------------------------------

@mcp.tool()
def get_horse_profile(horse_name: str) -> dict:
    """
    Get a detailed profile for a horse including career stats and full race history.

    Args:
        horse_name: Exact or partial horse name to look up. If multiple matches are
                    found, the first alphabetical match is used.

    Returns horse info, career stats (wins, places, shows, win %), and race history.
    """
    supabase = get_supabase_client()

    # Find horse by name (exact first, then partial)
    response = supabase.table('hranalyzer_horses') \
        .select('*') \
        .ilike('horse_name', horse_name) \
        .limit(1) \
        .execute()

    if not response.data:
        # Try partial match
        response = supabase.table('hranalyzer_horses') \
            .select('*') \
            .ilike('horse_name', f'%{horse_name}%') \
            .order('horse_name') \
            .limit(1) \
            .execute()

    if not response.data:
        return {"error": f"Horse not found: {horse_name}"}

    horse = response.data[0]

    # Get race entries
    entries_response = supabase.table('hranalyzer_race_entries') \
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
        ''') \
        .eq('horse_id', horse['id']) \
        .execute()

    race_history = []
    stats = {'total': 0, 'wins': 0, 'places': 0, 'shows': 0}

    for entry in entries_response.data:
        race = entry.get('race') or {}
        track = race.get('track') or {}
        jockey = entry.get('jockey') or {}
        trainer = entry.get('trainer') or {}

        race_history.append({
            'race_key': race.get('race_key'),
            'race_date': race.get('race_date'),
            'track_code': race.get('track_code'),
            'track_name': track.get('track_name', race.get('track_code')),
            'race_number': race.get('race_number'),
            'race_type': race.get('race_type'),
            'surface': race.get('surface'),
            'distance': race.get('distance'),
            'purse': race.get('purse'),
            'finish_position': entry.get('finish_position'),
            'final_odds': entry.get('final_odds'),
            'jockey_name': jockey.get('jockey_name', 'N/A'),
            'trainer_name': trainer.get('trainer_name', 'N/A'),
            'run_comments': entry.get('run_comments'),
            'scratched': entry.get('scratched', False),
            'race_status': race.get('race_status'),
        })

        if race.get('race_status') == 'completed' and not entry.get('scratched'):
            stats['total'] += 1
            pos = entry.get('finish_position')
            if pos == 1:
                stats['wins'] += 1
            elif pos == 2:
                stats['places'] += 1
            elif pos == 3:
                stats['shows'] += 1

    race_history.sort(key=lambda x: (x.get('race_date') or '', x.get('race_number') or 0), reverse=True)
    stats['win_percentage'] = round((stats['wins'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0

    return {
        "horse": {
            'name': horse['horse_name'],
            'sire': horse.get('sire'),
            'dam': horse.get('dam'),
            'sex': horse.get('sex'),
            'color': horse.get('color'),
            'foaling_year': horse.get('foaling_year'),
        },
        "stats": stats,
        "race_history": race_history,
    }


# ---------------------------------------------------------------------------
# Tool: get_scratches
# ---------------------------------------------------------------------------

@mcp.tool()
def get_scratches(view: str = "upcoming", limit: int = 50) -> dict:
    """
    Get scratched entries from races.

    Args:
        view: 'upcoming' for future scratches (default), or 'all' for historical.
        limit: Maximum number of results (default 50, max 200).

    Returns scratched horses with race info, track, and trainer.
    """
    supabase = get_supabase_client()
    today = date.today().isoformat()
    limit = min(limit, 200)

    query = supabase.table('hranalyzer_race_entries') \
        .select('''
            id, program_number, scratched, updated_at,
            horse:hranalyzer_horses(horse_name),
            trainer:hranalyzer_trainers(trainer_name),
            race:hranalyzer_races!inner(
                id, track_code, race_date, race_number, post_time, race_status,
                track:hranalyzer_tracks(track_name)
            )
        ''') \
        .eq('scratched', True)

    if view == 'upcoming':
        query = query.gte('race.race_date', today) \
            .order('race_date', foreign_table='race') \
            .order('track_code', foreign_table='race') \
            .order('race_number', foreign_table='race')
    else:
        query = query.lte('race.race_date', today) \
            .order('race_date', desc=True, foreign_table='race') \
            .order('track_code', foreign_table='race') \
            .order('race_number', foreign_table='race')

    response = query.limit(limit).execute()

    scratches = []
    for item in response.data:
        race = item.get('race') or {}
        track = race.get('track') or {}
        horse = item.get('horse') or {}
        trainer = item.get('trainer') or {}

        scratches.append({
            'race_date': race.get('race_date'),
            'track_code': race.get('track_code'),
            'track_name': track.get('track_name', race.get('track_code')),
            'race_number': race.get('race_number'),
            'post_time': format_to_12h(race.get('post_time')),
            'program_number': item['program_number'],
            'horse_name': horse.get('horse_name', 'Unknown'),
            'trainer_name': trainer.get('trainer_name', 'Unknown'),
        })

    return {"scratches": scratches, "count": len(scratches)}


# ---------------------------------------------------------------------------
# Tool: get_changes
# ---------------------------------------------------------------------------

@mcp.tool()
def get_changes(view: str = "upcoming", limit: int = 50) -> dict:
    """
    Get race changes including scratches, jockey changes, and other modifications.

    Args:
        view: 'upcoming' for future changes (default), or 'all' for historical.
        limit: Maximum number of results (default 50, max 200).

    Returns changes with type (scratch, jockey change, etc.), horse, race, and details.
    """
    supabase = get_supabase_client()
    today = date.today().isoformat()
    limit = min(limit, 200)

    # Get changes from the dedicated changes table
    query = supabase.table('hranalyzer_changes') \
        .select('''
            *,
            race:hranalyzer_races(
                race_key, track_code, race_date, race_number, post_time, race_status,
                track:hranalyzer_tracks(track_name)
            )
        ''') \
        .order('created_at', desc=True) \
        .limit(limit)

    if view == 'upcoming':
        query = query.gte('race.race_date', today)

    try:
        response = query.execute()
    except Exception:
        # Table might not exist, fall back gracefully
        return {"changes": [], "count": 0, "note": "Changes table not available"}

    changes = []
    for item in response.data:
        race = item.get('race') or {}
        track = race.get('track') or {}

        changes.append({
            'change_type': item.get('change_type', 'unknown'),
            'race_date': race.get('race_date'),
            'track_code': race.get('track_code'),
            'track_name': track.get('track_name', race.get('track_code')),
            'race_number': race.get('race_number'),
            'horse_name': item.get('horse_name'),
            'details': item.get('details'),
            'old_value': item.get('old_value'),
            'new_value': item.get('new_value'),
            'created_at': item.get('created_at'),
        })

    return {"changes": changes, "count": len(changes)}


# ---------------------------------------------------------------------------
# Tool: get_claims
# ---------------------------------------------------------------------------

@mcp.tool()
def get_claims(
    track: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
) -> dict:
    """
    Get claimed horses with new trainer, new owner, and claim price.

    Args:
        track: Filter by track code (e.g., 'GP'). Leave empty for all.
        start_date: Only include claims on or after this date (YYYY-MM-DD).
        end_date: Only include claims on or before this date (YYYY-MM-DD).
        limit: Maximum number of results (default 100, max 500).

    Returns a list of claimed horses with race info, new connections, and price.
    """
    supabase = get_supabase_client()
    limit = min(limit, 500)

    query = supabase.table('hranalyzer_claims') \
        .select('*, hranalyzer_races(race_key, track_code, race_date, race_number, hranalyzer_tracks(track_name))') \
        .order('created_at', desc=True) \
        .limit(limit)

    response = query.execute()

    claims = []
    for item in response.data:
        race = item.get('hranalyzer_races')
        if not race:
            continue

        track_info = race.get('hranalyzer_tracks')
        track_name = track_info.get('track_name') if track_info else race['track_code']

        # Python-side filters
        if track and race['track_code'] != track and track_name != track:
            continue
        if start_date and race['race_date'] < start_date:
            continue
        if end_date and race['race_date'] > end_date:
            continue

        claims.append({
            'race_key': race['race_key'],
            'race_date': race['race_date'],
            'track_code': race['track_code'],
            'track_name': track_name,
            'race_number': race['race_number'],
            'horse_name': item['horse_name'],
            'program_number': item.get('program_number'),
            'new_trainer': item['new_trainer_name'],
            'new_owner': item['new_owner_name'],
            'claim_price': item['claim_price'],
        })

    return {"claims": claims, "count": len(claims)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting TrackData MCP Server on port 8001...")
    print("Connect your AI agent to: http://localhost:8001/mcp")
    mcp.run(transport="streamable-http")
