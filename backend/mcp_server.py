"""
MCP Server for TrackData.live.
Provides read-only tools for AI agents to query horse racing data.
Runs alongside the Flask backend on port 8001.
"""

import os
import re
import sys
from datetime import date, datetime, timedelta

import pytz
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Import the shared Supabase client
sys.path.insert(0, os.path.dirname(__file__))
from supabase_client import get_supabase_client
from runtime_state import summarize_freshness


mcp = FastMCP(
    "TrackData",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=8001,
)


def format_to_12h(time_str):
    """Convert 24h time string (HH:MM:SS) to 12h format (I:MM PM)."""
    if not time_str or time_str in {"N/A", "TBD"}:
        return time_str

    clean_time = str(time_str).replace("Post Time", "").replace("Post time", "").strip()
    clean_time = clean_time.replace("ET", "").replace("PT", "").replace("CT", "").replace("MT", "").strip()

    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            parsed = datetime.strptime(clean_time, fmt)
            return parsed.strftime("%-I:%M %p")
        except ValueError:
            continue
    return time_str


def parse_post_time_to_iso(race_date_str, post_time_str, tz_name="America/New_York"):
    """Convert race date and post time string to ISO 8601 with timezone."""
    if not post_time_str or post_time_str in {"N/A", "TBD"}:
        return None

    clean_time = str(post_time_str).replace("Post Time", "").replace("Post time", "").strip()
    clean_time = clean_time.replace("ET", "").replace("PT", "").replace("CT", "").replace("MT", "").strip()

    parsed_time = None
    for fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S", "%I:%M%p"):
        try:
            parsed_time = datetime.strptime(clean_time, fmt).time()
            break
        except ValueError:
            continue

    if parsed_time and race_date_str:
        try:
            target_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
            localized = pytz.timezone(tz_name or "America/New_York").localize(
                datetime.combine(target_date, parsed_time)
            )
            return localized.isoformat()
        except Exception:
            return None
    return None


def derive_live_race_status(
    race_date_str,
    post_time_str,
    stored_status,
    tz_name="America/New_York",
    has_results=False,
    grace_minutes=20,
):
    """Derive a live race status from stored state plus post time."""
    if has_results or stored_status == "completed":
        return "completed"
    if stored_status in {"cancelled", "delayed"}:
        return stored_status
    if stored_status == "past_drf_only":
        return "past"

    post_time_iso = parse_post_time_to_iso(race_date_str, post_time_str, tz_name)
    if not post_time_iso:
        return stored_status or "upcoming"

    try:
        post_dt = datetime.fromisoformat(post_time_iso)
        now_dt = datetime.now(post_dt.tzinfo)
        if now_dt >= post_dt + timedelta(minutes=grace_minutes):
            return "past"
    except Exception:
        return stored_status or "upcoming"

    return "upcoming"


def is_valid_horse_name(name):
    """Filter obvious garbage names from horse listings."""
    if not name or len(name) < 2:
        return False
    if name.startswith("$") or name.startswith("-"):
        return False
    if re.match(r"^[\d\s\.\,\-\$]+$", name):
        return False
    if name in {"-", "--", "N/A", "Unknown", "TBD"}:
        return False
    return True


def normalize_identity(item):
    """Create a stable identity for a change record."""
    pgm = str(item.get("program_number") or "").strip().upper().lstrip("0")
    if pgm in {"-", "NONE", "NULL"}:
        pgm = ""

    horse_name = str(item.get("horse_name") or "").strip().lower()
    if horse_name in {"", "race-wide", "unknown", "none", "null"}:
        horse_name = "RACE_WIDE"

    if pgm:
        return f"PGM_{pgm}"
    return horse_name


def get_type_class(item):
    """Classify changes for deduplication."""
    change_type = (item.get("change_type") or "").lower()
    description = (item.get("description") or "").lower()
    is_scratch_related = "scratch" in change_type or ("scratch" in description and "reason" in description)

    if is_scratch_related:
        return "scratch"
    if "jockey" in change_type:
        return "jockey"
    if "weight" in change_type:
        return "weight"
    if "cancelled" in change_type:
        return "cancelled"
    return "other"


def _chunked(values, size=200):
    """Yield fixed-size chunks from an iterable of values."""
    values = list(values)
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _extract_nested_name(payload, *keys):
    """Return the first non-empty nested name value from a relation payload."""
    payload = payload or {}
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return None


def _get_entry_snapshot(item, entry_snapshots):
    """Resolve an entry snapshot from inline data first, then the bulk lookup map."""
    entry = item.get("entry") or {}
    horse = entry.get("horse") or entry.get("hranalyzer_horses") or {}
    jockey = entry.get("jockey") or entry.get("hranalyzer_jockeys") or {}
    trainer = entry.get("trainer") or entry.get("hranalyzer_trainers") or {}

    inline_snapshot = {
        "id": item.get("entry_id") or entry.get("id"),
        "program_number": entry.get("program_number"),
        "horse_name": _extract_nested_name(horse, "horse_name"),
        "jockey_name": _extract_nested_name(jockey, "jockey_name"),
        "trainer_name": _extract_nested_name(trainer, "trainer_name"),
        "weight": entry.get("weight"),
    }

    entry_id = item.get("entry_id") or entry.get("id")
    snapshot = dict(entry_snapshots.get(entry_id, {}))
    for key, value in inline_snapshot.items():
        if value not in (None, "", []):
            snapshot[key] = value
    return snapshot


def _get_race_snapshot(item, race_snapshots):
    """Resolve a race snapshot from inline data first, then the bulk lookup map."""
    race = item.get("race") or {}
    track = race.get("track") or race.get("hranalyzer_tracks") or {}

    inline_snapshot = {
        "id": item.get("race_id") or race.get("id"),
        "race_key": race.get("race_key"),
        "track_code": race.get("track_code"),
        "track_name": _extract_nested_name(track, "track_name"),
        "race_date": race.get("race_date"),
        "race_number": race.get("race_number"),
        "post_time": race.get("post_time"),
    }

    race_id = item.get("race_id") or race.get("id")
    snapshot = dict(race_snapshots.get(race_id, {}))
    for key, value in inline_snapshot.items():
        if value not in (None, "", []):
            snapshot[key] = value
    return snapshot


def _fetch_entry_snapshots(supabase, entry_ids):
    """Bulk-load race entry details needed to enrich change rows."""
    snapshots = {}
    if not entry_ids:
        return snapshots

    for chunk in _chunked(sorted({entry_id for entry_id in entry_ids if entry_id}), size=200):
        response = (
            supabase.table("hranalyzer_race_entries")
            .select(
                """
                    id,
                    race_id,
                    program_number,
                    weight,
                    horse:hranalyzer_horses(horse_name),
                    jockey:hranalyzer_jockeys(jockey_name),
                    trainer:hranalyzer_trainers(trainer_name)
                """
            )
            .in_("id", chunk)
            .execute()
        )

        for row in response.data or []:
            horse = row.get("horse") or row.get("hranalyzer_horses") or {}
            jockey = row.get("jockey") or row.get("hranalyzer_jockeys") or {}
            trainer = row.get("trainer") or row.get("hranalyzer_trainers") or {}
            snapshots[row["id"]] = {
                "id": row["id"],
                "race_id": row.get("race_id"),
                "program_number": row.get("program_number"),
                "horse_name": _extract_nested_name(horse, "horse_name"),
                "jockey_name": _extract_nested_name(jockey, "jockey_name"),
                "trainer_name": _extract_nested_name(trainer, "trainer_name"),
                "weight": row.get("weight"),
            }

    return snapshots


def _fetch_race_snapshots(supabase, race_ids):
    """Bulk-load race details needed to enrich change rows."""
    snapshots = {}
    if not race_ids:
        return snapshots

    for chunk in _chunked(sorted({race_id for race_id in race_ids if race_id}), size=200):
        response = (
            supabase.table("hranalyzer_races")
            .select(
                """
                    id,
                    race_key,
                    track_code,
                    race_date,
                    race_number,
                    post_time,
                    track:hranalyzer_tracks(track_name)
                """
            )
            .in_("id", chunk)
            .execute()
        )

        for row in response.data or []:
            track = row.get("track") or row.get("hranalyzer_tracks") or {}
            snapshots[row["id"]] = {
                "id": row["id"],
                "race_key": row.get("race_key"),
                "track_code": row.get("track_code"),
                "track_name": _extract_nested_name(track, "track_name"),
                "race_date": row.get("race_date"),
                "race_number": row.get("race_number"),
                "post_time": row.get("post_time"),
            }

    return snapshots


def _build_change_record(item, entry_snapshots, race_snapshots, source, default_change_type=None):
    """Normalize a raw change row into the shared MCP/API change shape."""
    entry = _get_entry_snapshot(item, entry_snapshots)
    race = _get_race_snapshot(item, race_snapshots)

    return {
        "id": item["id"],
        "race_id": race.get("id") or item.get("race_id"),
        "race_key": race.get("race_key"),
        "race_date": str(race.get("race_date")) if race.get("race_date") is not None else None,
        "track_code": race.get("track_code"),
        "track_name": race.get("track_name") or race.get("track_code"),
        "race_number": race.get("race_number"),
        "post_time": race.get("post_time", "N/A"),
        "entry_id": entry.get("id") or item.get("entry_id"),
        "program_number": entry.get("program_number", item.get("program_number", "-")),
        "horse_name": entry.get("horse_name") or item.get("horse_name", "Race-wide"),
        "jockey_name": entry.get("jockey_name"),
        "trainer_name": entry.get("trainer_name"),
        "weight": entry.get("weight"),
        "change_type": default_change_type or item.get("change_type"),
        "description": item.get("description"),
        "change_time": item.get("created_at") or item.get("change_time") or item.get("updated_at"),
        "_source": source,
    }


def _resolve_date_filtered_query(query, mode, today, start_date="", end_date=""):
    """Apply date filtering to a Supabase query."""
    if start_date:
        query = query.gte("race.race_date", start_date)
    elif mode == "upcoming":
        query = query.eq("race.race_date", today)
    elif mode == "history":
        query = query.lt("race.race_date", today)

    if end_date:
        query = query.lte("race.race_date", end_date)

    return query


def _build_feed_metadata(items, requested_view, applied_view, fallback_applied=False, fallback_reason=""):
    dates = [item.get("race_date") for item in items if item.get("race_date")]
    return {
        "requested_view": requested_view,
        "applied_view": applied_view,
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason or None,
        "latest_race_date": max(dates) if dates else None,
        "earliest_race_date": min(dates) if dates else None,
    }


def _track_matches(track_filter, race_track_code, race_track_name):
    if not track_filter:
        return True
    return track_filter in {race_track_code, race_track_name}


def fetch_change_feed(mode="upcoming", page=1, limit=20, track="All", start_date="", end_date="", race_number=0):
    """Mirror backend change merge and dedupe logic for MCP consumers."""
    supabase = get_supabase_client()
    today = date.today().isoformat()
    start = max(page - 1, 0) * limit
    end = start + limit
    all_changes = []
    entries_with_detailed_scratches = set()

    try:
        changes_query = (
            supabase.table("hranalyzer_changes")
            .select(
                """
                    id,
                    entry_id,
                    race_id,
                    change_type,
                    description,
                    created_at,
                    race:hranalyzer_races!inner(id)
                """
            )
        )

        changes_query = _resolve_date_filtered_query(
            changes_query,
            mode,
            today,
            start_date=start_date,
            end_date=end_date,
        )

        if track != "All":
            changes_query = changes_query.eq("race.track_code", track)
        if race_number:
            changes_query = changes_query.eq("race.race_number", race_number)

        changes_response = changes_query.execute()
        change_rows = changes_response.data or []
        entry_snapshots = _fetch_entry_snapshots(
            supabase,
            [item.get("entry_id") for item in change_rows if item.get("entry_id")],
        )
        race_snapshots = _fetch_race_snapshots(
            supabase,
            [
                item.get("race_id") or (item.get("race") or {}).get("id")
                for item in change_rows
                if item.get("race_id") or (item.get("race") or {}).get("id")
            ],
        )

        for item in change_rows:

            if item.get("change_type") == "Scratch" and item.get("entry_id"):
                entries_with_detailed_scratches.add(item["entry_id"])

            all_changes.append(_build_change_record(item, entry_snapshots, race_snapshots, "changes"))
    except Exception:
        pass

    scratch_query = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                id,
                race_id,
                program_number,
                scratched,
                updated_at,
                race:hranalyzer_races!inner(id)
            """
        )
        .eq("scratched", True)
    )

    scratch_query = _resolve_date_filtered_query(
        scratch_query,
        mode,
        today,
        start_date=start_date,
        end_date=end_date,
    )

    if track != "All":
        scratch_query = scratch_query.eq("race.track_code", track)
    if race_number:
        scratch_query = scratch_query.eq("race.race_number", race_number)

    scratch_response = scratch_query.execute()
    scratch_rows = scratch_response.data or []
    scratch_entry_snapshots = _fetch_entry_snapshots(supabase, [item["id"] for item in scratch_rows if item.get("id")])
    scratch_race_snapshots = _fetch_race_snapshots(
        supabase,
        [
            item.get("race_id") or (item.get("race") or {}).get("id")
            for item in scratch_rows
            if item.get("race_id") or (item.get("race") or {}).get("id")
        ],
    )

    for item in scratch_rows:
        if item["id"] in entries_with_detailed_scratches:
            continue

        all_changes.append(
            _build_change_record(
                item,
                scratch_entry_snapshots,
                scratch_race_snapshots,
                "entries",
                default_change_type="Scratch",
            )
        )

    normalized_map = {}
    for item in all_changes:
        key_base = (
            str(item.get("track_code") or "").strip().upper(),
            str(item.get("race_date") or "").strip()[:10],
            str(item.get("race_number") or "").strip(),
            normalize_identity(item),
            get_type_class(item),
        )

        if key_base[3] == "RACE_WIDE":
            event_key = key_base + ((item.get("description") or "").strip()[:30].lower(),)
        else:
            event_key = key_base

        normalized_map.setdefault(event_key, []).append(item)

    final_list = []
    for candidates in normalized_map.values():
        if not candidates:
            continue

        if len(candidates) == 1:
            winner = candidates[0]
        else:
            candidates.sort(key=lambda candidate: str(candidate.get("change_time") or ""), reverse=True)
            winner = candidates[0]

        if get_type_class(winner) == "scratch" and winner.get("change_type") == "Other":
            winner["change_type"] = "Scratch"

        final_list.append(winner)

    final_list = [
        item
        for item in final_list
        if item.get("horse_name") not in (None, "", "Race-wide", "Race-Wide")
        or item.get("change_type") == "Race Cancelled"
    ]
    final_list = [
        item
        for item in final_list
        if item.get("change_type") != "Wagering"
        and "wagering" not in (item.get("description") or "").lower()
    ]

    sort_desc = mode in {"history", "all"} or bool(start_date or end_date)
    if sort_desc:
        final_list.sort(
            key=lambda item: (
                str(item.get("race_date") or ""),
                str(item.get("track_code") or ""),
                int(str(item.get("race_number") or 0)),
                normalize_identity(item),
            ),
            reverse=True,
        )
    else:
        final_list.sort(
            key=lambda item: (
                str(item.get("race_date") or ""),
                str(item.get("track_code") or ""),
                int(str(item.get("race_number") or 0)),
                normalize_identity(item),
            )
        )

    paginated = final_list[start:end]
    for item in paginated:
        item.pop("_source", None)

    return {
        "changes": paginated,
        "count": len(final_list),
        "page": page,
        "limit": limit,
        "total_pages": (len(final_list) + limit - 1) // limit if limit > 0 else 1,
    }


@mcp.tool()
def get_health() -> dict:
    """Check database connectivity and MCP server health."""
    try:
        supabase = get_supabase_client()
        supabase.table("hranalyzer_tracks").select("id").limit(1).execute()
        return {"status": "healthy", "database": "connected", "version": "1.0.3"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


@mcp.tool()
def get_tracks() -> dict:
    """Get all available horse racing tracks."""
    supabase = get_supabase_client()
    response = (
        supabase.table("hranalyzer_tracks")
        .select("track_code, track_name, location, timezone")
        .order("track_name")
        .execute()
    )
    return {"tracks": response.data, "count": len(response.data)}


@mcp.tool()
def get_recent_uploads(limit: int = 10) -> dict:
    """Get recent DRF uploads tracked by the platform."""
    supabase = get_supabase_client()
    limit = min(max(limit, 1), 100)
    response = (
        supabase.table("hranalyzer_upload_logs")
        .select("*")
        .order("uploaded_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"uploads": response.data, "count": len(response.data), "limit": limit}


@mcp.tool()
def get_filter_options(summary_date: str = "") -> dict:
    """Get available dates, tracks, and per-track summary for a target date."""
    supabase = get_supabase_client()
    today = date.today().isoformat()
    target_summary_date = summary_date or today

    dates_response = supabase.table("hranalyzer_races").select("race_date").order("race_date", desc=True).execute()
    unique_dates = sorted({row["race_date"] for row in dates_response.data if row["race_date"] <= today}, reverse=True)

    tracks_response = supabase.table("hranalyzer_races").select("track_code, hranalyzer_tracks(track_name)").execute()
    unique_tracks = {}
    for row in tracks_response.data:
        track_code = row["track_code"]
        track_name = (row.get("hranalyzer_tracks") or {}).get("track_name", track_code)
        unique_tracks[track_name] = track_code

    sorted_tracks = [{"name": name, "code": unique_tracks[name]} for name in sorted(unique_tracks)]

    summary_response = (
        supabase.table("hranalyzer_races")
        .select(
            "*, hranalyzer_tracks(track_name, timezone), "
            "hranalyzer_race_entries(finish_position, hranalyzer_horses(horse_name))"
        )
        .eq("race_date", target_summary_date)
        .order("race_number")
        .execute()
    )

    summary_map = {}
    for race in summary_response.data:
        track_name = (race.get("hranalyzer_tracks") or {}).get("track_name", race["track_code"])
        entries = race.get("hranalyzer_race_entries") or []
        has_results = any(entry.get("finish_position") in [1, 2, 3] for entry in entries)
        timezone_name = (race.get("hranalyzer_tracks") or {}).get("timezone", "America/New_York")
        race_status = derive_live_race_status(
            race["race_date"],
            race.get("post_time"),
            race["race_status"],
            timezone_name,
            has_results=has_results,
        )

        if track_name not in summary_map:
            summary_map[track_name] = {
                "track_name": track_name,
                "track_code": race["track_code"],
                "total": 0,
                "upcoming": 0,
                "past_post": 0,
                "completed": 0,
                "cancelled": 0,
                "is_fully_cancelled": False,
                "next_race_time": None,
                "next_race_iso": None,
                "last_race_winner": None,
                "last_race_number": 0,
            }

        summary_map[track_name]["total"] += 1

        if race_status == "completed":
            summary_map[track_name]["completed"] += 1
            if race["race_number"] > summary_map[track_name]["last_race_number"]:
                summary_map[track_name]["last_race_number"] = race["race_number"]
                winner_entry = next(
                    (entry for entry in entries if entry.get("finish_position") == 1),
                    None,
                )
                if winner_entry and winner_entry.get("hranalyzer_horses"):
                    summary_map[track_name]["last_race_winner"] = winner_entry["hranalyzer_horses"]["horse_name"]
                else:
                    summary_map[track_name]["last_race_winner"] = "Unknown"
        elif race_status == "cancelled":
            summary_map[track_name]["cancelled"] += 1
        elif race_status == "upcoming":
            summary_map[track_name]["upcoming"] += 1
            post_time_iso = parse_post_time_to_iso(target_summary_date, race.get("post_time"), timezone_name)
            if post_time_iso:
                current_next_iso = summary_map[track_name]["next_race_iso"]
                if current_next_iso is None or post_time_iso < current_next_iso:
                    summary_map[track_name]["next_race_iso"] = post_time_iso
                    summary_map[track_name]["next_race_time"] = format_to_12h(race.get("post_time"))
        else:
            summary_map[track_name]["past_post"] += 1

    for summary in summary_map.values():
        if summary["total"] > 0 and summary["cancelled"] == summary["total"]:
            summary["is_fully_cancelled"] = True

    return {
        "dates": unique_dates,
        "tracks": sorted_tracks,
        "today_summary": sorted(summary_map.values(), key=lambda item: item["track_name"]),
        "summary_date": target_summary_date,
    }


@mcp.tool()
def get_feed_freshness() -> dict:
    """Expose crawler freshness and open alerts directly to MCP consumers."""
    freshness, alerts = summarize_freshness()
    open_alerts = [alert for alert in alerts if alert.get("status") == "open"]
    crawler = {}
    stale_crawlers = []
    fresh_crawlers = []
    warming_up_crawlers = []
    in_progress_crawlers = []

    for crawl_name, item in freshness.items():
        crawl_status = "fresh"
        if item.get("within_startup_grace") and not item.get("last_success_at"):
            crawl_status = "warming_up"
            warming_up_crawlers.append(crawl_name)
        elif item.get("stale"):
            crawl_status = "stale"
            stale_crawlers.append(crawl_name)
        elif item.get("in_progress"):
            crawl_status = "in_progress"
            in_progress_crawlers.append(crawl_name)
        else:
            fresh_crawlers.append(crawl_name)

        crawler[crawl_name] = {**item, "status": crawl_status}

    if stale_crawlers:
        overall_status = "stale"
        summary = f"Stale crawlers: {', '.join(stale_crawlers)}."
    elif warming_up_crawlers:
        overall_status = "warming_up"
        summary = (
            "Crawler startup grace is active. Freshness timestamps may still be empty while services warm up."
        )
    elif open_alerts:
        overall_status = "degraded"
        summary = f"There are {len(open_alerts)} open runtime alert(s), but crawler freshness is current."
    elif in_progress_crawlers:
        overall_status = "healthy"
        summary = f"All crawlers are healthy. Active crawl(s): {', '.join(in_progress_crawlers)}."
    else:
        overall_status = "healthy"
        summary = "All crawler freshness checks are healthy."

    return {
        "crawler": crawler,
        "alerts": open_alerts,
        "status": overall_status,
        "summary": summary,
        "all_crawlers_fresh": not stale_crawlers and not warming_up_crawlers,
        "stale_crawlers": stale_crawlers,
        "fresh_crawlers": fresh_crawlers,
        "warming_up_crawlers": warming_up_crawlers,
        "in_progress_crawlers": in_progress_crawlers,
        "alert_count": len(open_alerts),
        "how_to_read": (
            "Use status and stale_crawlers first. Per-crawler status will be one of fresh, in_progress, "
            "warming_up, or stale."
        ),
    }


@mcp.tool()
def get_entries(
    track: str = "",
    race_date: str = "",
    race_number: int = 0,
    include_scratched: bool = True,
    limit: int = 20,
) -> dict:
    """Get card entries for a specific date/track/race slice."""
    supabase = get_supabase_client()
    target_date = race_date or date.today().isoformat()
    limit = min(max(limit, 1), 100)

    query = (
        supabase.table("hranalyzer_races")
        .select("*, hranalyzer_tracks(track_name, location, timezone)")
        .eq("race_date", target_date)
        .order("race_number")
    )
    if track and len(track) <= 4 and track.upper() == track:
        query = query.eq("track_code", track)
    if race_number:
        query = query.eq("race_number", race_number)

    raw_races = query.limit(limit).execute().data or []
    filtered_races = [
        race for race in raw_races
        if _track_matches(track, race.get("track_code"), (race.get("hranalyzer_tracks") or {}).get("track_name"))
    ]

    if not filtered_races:
        return {"entries": [], "count": 0, "race_date": target_date}

    race_ids = [race["id"] for race in filtered_races]
    entries_rows = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                race_id, id, program_number, post_position, morning_line_odds, final_odds,
                scratched, weight, medication, equipment,
                hranalyzer_horses(horse_name),
                hranalyzer_jockeys(jockey_name),
                hranalyzer_trainers(trainer_name)
            """
        )
        .in_("race_id", race_ids)
        .order("program_number")
        .execute()
        .data
        or []
    )

    entries_by_race = {}
    for row in entries_rows:
        if not include_scratched and row.get("scratched"):
            continue
        entries_by_race.setdefault(row["race_id"], []).append(
            {
                "id": row["id"],
                "program_number": row.get("program_number"),
                "post_position": row.get("post_position"),
                "horse_name": (row.get("hranalyzer_horses") or {}).get("horse_name", "Unknown"),
                "jockey_name": (row.get("hranalyzer_jockeys") or {}).get("jockey_name", "N/A"),
                "trainer_name": (row.get("hranalyzer_trainers") or {}).get("trainer_name", "N/A"),
                "morning_line_odds": row.get("morning_line_odds"),
                "final_odds": row.get("final_odds"),
                "scratched": row.get("scratched", False),
                "weight": row.get("weight"),
                "medication": row.get("medication"),
                "equipment": row.get("equipment"),
            }
        )

    payload = []
    for race in filtered_races:
        track_info = race.get("hranalyzer_tracks") or {}
        payload.append(
            {
                "race_key": race["race_key"],
                "track_code": race["track_code"],
                "track_name": track_info.get("track_name", race["track_code"]),
                "race_date": race["race_date"],
                "race_number": race["race_number"],
                "post_time": format_to_12h(race.get("post_time")),
                "race_type": race.get("race_type"),
                "surface": race.get("surface"),
                "distance": race.get("distance"),
                "purse": race.get("purse"),
                "race_status": race.get("race_status"),
                "entries": entries_by_race.get(race["id"], []),
            }
        )

    return {"entries": payload, "count": len(payload), "race_date": target_date}


@mcp.tool()
def get_results(track: str = "", race_date: str = "", race_number: int = 0, limit: int = 20) -> dict:
    """Get result summaries for exact race/date filters without full race-detail fetches."""
    supabase = get_supabase_client()
    target_date = race_date or date.today().isoformat()
    limit = min(max(limit, 1), 100)

    query = (
        supabase.table("hranalyzer_races")
        .select("*, hranalyzer_tracks(track_name, location, timezone)")
        .eq("race_date", target_date)
        .order("race_number")
    )
    if track and len(track) <= 4 and track.upper() == track:
        query = query.eq("track_code", track)
    if race_number:
        query = query.eq("race_number", race_number)

    raw_races = query.limit(limit).execute().data or []
    filtered_races = [
        race for race in raw_races
        if _track_matches(track, race.get("track_code"), (race.get("hranalyzer_tracks") or {}).get("track_name"))
    ]

    if not filtered_races:
        return {"results": [], "count": 0, "race_date": target_date}

    race_ids = [race["id"] for race in filtered_races]
    entries_rows = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                race_id, program_number, finish_position, final_odds,
                win_payout, place_payout, show_payout,
                hranalyzer_horses(horse_name),
                hranalyzer_trainers(trainer_name)
            """
        )
        .in_("race_id", race_ids)
        .execute()
        .data
        or []
    )

    results_by_race = {}
    for row in entries_rows:
        if row.get("finish_position") in [1, 2, 3]:
            results_by_race.setdefault(row["race_id"], []).append(
                {
                    "position": row["finish_position"],
                    "program_number": row.get("program_number"),
                    "horse_name": (row.get("hranalyzer_horses") or {}).get("horse_name", "Unknown"),
                    "trainer_name": (row.get("hranalyzer_trainers") or {}).get("trainer_name", "N/A"),
                    "final_odds": row.get("final_odds"),
                    "win_payout": row.get("win_payout"),
                    "place_payout": row.get("place_payout"),
                    "show_payout": row.get("show_payout"),
                }
            )

    payload = []
    for race in filtered_races:
        top_finishers = sorted(results_by_race.get(race["id"], []), key=lambda item: item["position"])
        track_info = race.get("hranalyzer_tracks") or {}
        payload.append(
            {
                "race_key": race["race_key"],
                "track_code": race["track_code"],
                "track_name": track_info.get("track_name", race["track_code"]),
                "race_date": race["race_date"],
                "race_number": race["race_number"],
                "post_time": format_to_12h(race.get("post_time")),
                "race_status": derive_live_race_status(
                    race["race_date"],
                    race.get("post_time"),
                    race.get("race_status"),
                    track_info.get("timezone", "America/New_York"),
                    has_results=bool(top_finishers),
                ),
                "final_time": race.get("final_time"),
                "winner_program_number": race.get("winner_program_number"),
                "winner": top_finishers[0]["horse_name"] if top_finishers else None,
                "results": top_finishers,
            }
        )

    return {"results": payload, "count": len(payload), "race_date": target_date}


@mcp.tool()
def get_todays_races(track: str = "", status: str = "All") -> dict:
    """Get today's races with backend-parity fields and top-3 results when available."""
    supabase = get_supabase_client()
    today = date.today().isoformat()

    raw_races = (
        supabase.table("hranalyzer_races")
        .select("*, hranalyzer_tracks(track_name, location, timezone)")
        .eq("race_date", today)
        .order("race_number")
        .execute()
        .data
    )

    if not raw_races:
        return {"races": [], "count": 0, "date": today}

    race_ids = [race["id"] for race in raw_races]
    entries = (
        supabase.table("hranalyzer_race_entries")
        .select(
            "race_id, id, program_number, finish_position, "
            "hranalyzer_horses(horse_name), hranalyzer_trainers(trainer_name)"
        )
        .in_("race_id", race_ids)
        .execute()
        .data
    )
    claims = (
        supabase.table("hranalyzer_claims").select("race_id").in_("race_id", race_ids).execute().data
    )
    races_with_claims = {claim["race_id"] for claim in claims}

    race_stats = {}
    for entry in entries:
        race_id = entry["race_id"]
        race_stats.setdefault(race_id, {"count": 0, "results": []})
        race_stats[race_id]["count"] += 1

        if entry.get("finish_position") in [1, 2, 3]:
            race_stats[race_id]["results"].append(
                {
                    "position": entry["finish_position"],
                    "horse": (entry.get("hranalyzer_horses") or {}).get("horse_name", "Unknown"),
                    "number": entry.get("program_number"),
                    "trainer": (entry.get("hranalyzer_trainers") or {}).get("trainer_name", "N/A"),
                }
            )

    for stats in race_stats.values():
        stats["results"].sort(key=lambda item: item["position"])

    races = []
    for race in raw_races:
        track_name = (race.get("hranalyzer_tracks") or {}).get("track_name", race["track_code"])
        if track and track != "All" and track_name != track and race["track_code"] != track:
            continue

        stats = race_stats.get(race["id"], {"count": 0, "results": []})
        current_status = derive_live_race_status(
            race["race_date"],
            race.get("post_time"),
            race["race_status"],
            (race.get("hranalyzer_tracks") or {}).get("timezone", "America/New_York"),
            has_results=bool(stats["results"]),
        )

        if status and status != "All":
            if status == "Upcoming" and current_status != "upcoming":
                continue
            if status == "Completed" and current_status != "completed":
                continue

        races.append(
            {
                "race_key": race["race_key"],
                "track_code": race["track_code"],
                "track_name": track_name,
                "race_number": race["race_number"],
                "race_date": race["race_date"],
                "post_time": format_to_12h(race.get("post_time")),
                "post_time_iso": parse_post_time_to_iso(
                    race["race_date"],
                    race.get("post_time"),
                    (race.get("hranalyzer_tracks") or {}).get("timezone", "America/New_York"),
                ),
                "race_type": race.get("race_type"),
                "surface": race.get("surface"),
                "distance": race.get("distance"),
                "purse": race.get("purse"),
                "entry_count": stats["count"],
                "race_status": current_status,
                "has_claims": race["id"] in races_with_claims,
                "results": stats["results"],
                "id": race["id"],
            }
        )

    return {"races": races, "count": len(races), "date": today}


@mcp.tool()
def get_past_races(track: str = "", start_date: str = "", end_date: str = "", limit: int = 50) -> dict:
    """Get past races with backend-parity fields and top-3 finishers."""
    supabase = get_supabase_client()
    today = date.today().isoformat()
    limit = min(max(limit, 1), 200)

    query = (
        supabase.table("hranalyzer_races")
        .select(
            """
                *,
                track:hranalyzer_tracks(track_name, location),
                results:hranalyzer_race_entries(
                    finish_position,
                    program_number,
                    horse:hranalyzer_horses(horse_name),
                    trainer:hranalyzer_trainers(trainer_name)
                ),
                claims:hranalyzer_claims(id),
                all_entries:hranalyzer_race_entries(id)
            """
        )
        .lte("race_date", today)
        .order("race_date", desc=True)
        .order("race_number", desc=False)
        .in_("race_status", ["completed", "past_drf_only", "cancelled"])
    )

    if track:
        query = query.eq("track_code", track)
    if start_date:
        query = query.gte("race_date", start_date)
    if end_date:
        query = query.lte("race_date", end_date)

    response = query.limit(limit).execute()
    races = []

    for race in response.data:
        formatted_results = []
        winner_name = "N/A"
        winner_program_number = race.get("winner_program_number")
        calculated_winner_program_number = None

        for result in race.get("results", []):
            if result.get("finish_position") in [1, 2, 3]:
                horse_name = (result.get("horse") or {}).get("horse_name", "Unknown")
                trainer_name = (result.get("trainer") or {}).get("trainer_name", "N/A")
                formatted_results.append(
                    {
                        "position": result["finish_position"],
                        "horse": horse_name,
                        "number": result.get("program_number"),
                        "trainer": trainer_name,
                    }
                )
                if result["finish_position"] == 1:
                    winner_name = horse_name
                    calculated_winner_program_number = result.get("program_number")

        formatted_results.sort(key=lambda item: item["position"])
        if not winner_program_number:
            winner_program_number = calculated_winner_program_number

        races.append(
            {
                "race_key": race["race_key"],
                "track_code": race["track_code"],
                "track_name": (race.get("track") or {}).get("track_name", race["track_code"]),
                "race_number": race["race_number"],
                "race_date": race["race_date"],
                "post_time": format_to_12h(race.get("post_time")),
                "race_type": race.get("race_type"),
                "surface": race.get("surface"),
                "distance": race.get("distance"),
                "purse": race.get("purse"),
                "entry_count": len(race.get("all_entries", [])),
                "race_status": race["race_status"],
                "has_claims": len(race.get("claims", [])) > 0,
                "data_source": race.get("data_source"),
                "id": race["id"],
                "winner": winner_name,
                "winner_program_number": winner_program_number,
                "results": formatted_results,
                "time": race.get("final_time") or "N/A",
                "link": race.get("equibase_chart_url", "#"),
            }
        )

    return {"races": races, "count": len(races)}


@mcp.tool()
def get_race_details(race_key: str) -> dict:
    """Get detailed race data, entries, payouts, claims, and sibling navigation."""
    supabase = get_supabase_client()

    race_response = (
        supabase.table("hranalyzer_races")
        .select("*, hranalyzer_tracks(track_name, location, timezone)")
        .eq("race_key", race_key)
        .single()
        .execute()
    )

    if not race_response.data:
        return {"error": f"Race not found: {race_key}"}

    race = race_response.data
    entries_response = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                *,
                hranalyzer_horses(horse_name, sire, dam, color, sex),
                hranalyzer_jockeys(jockey_name),
                hranalyzer_trainers(trainer_name),
                hranalyzer_owners(owner_name)
            """
        )
        .eq("race_id", race["id"])
        .order("program_number")
        .execute()
    )

    entries = []
    for entry in entries_response.data:
        horse = entry.get("hranalyzer_horses") or {}
        jockey = entry.get("hranalyzer_jockeys") or {}
        trainer = entry.get("hranalyzer_trainers") or {}
        owner = entry.get("hranalyzer_owners") or {}
        entries.append(
            {
                "id": entry["id"],
                "program_number": entry.get("program_number"),
                "post_position": entry.get("post_position"),
                "horse_name": horse.get("horse_name", "Unknown"),
                "horse_info": {
                    "sire": horse.get("sire"),
                    "dam": horse.get("dam"),
                    "color": horse.get("color"),
                    "sex": horse.get("sex"),
                },
                "jockey_id": entry.get("jockey_id"),
                "jockey_name": jockey.get("jockey_name", "N/A"),
                "trainer_id": entry.get("trainer_id"),
                "trainer_name": trainer.get("trainer_name", "N/A"),
                "owner_name": owner.get("owner_name", "N/A"),
                "morning_line_odds": entry.get("morning_line_odds"),
                "final_odds": entry.get("final_odds"),
                "weight": entry.get("weight"),
                "medication": entry.get("medication"),
                "equipment": entry.get("equipment"),
                "scratched": entry.get("scratched", False),
                "finish_position": entry.get("finish_position"),
                "official_position": entry.get("official_position"),
                "run_comments": entry.get("run_comments"),
                "win_payout": entry.get("win_payout"),
                "place_payout": entry.get("place_payout"),
                "show_payout": entry.get("show_payout"),
            }
        )

    exotic_payouts = []
    claims = []
    if race["race_status"] == "completed":
        exotic_payouts = (
            supabase.table("hranalyzer_exotic_payouts").select("*").eq("race_id", race["id"]).execute().data
        )
        claims = supabase.table("hranalyzer_claims").select("*").eq("race_id", race["id"]).execute().data

    siblings = (
        supabase.table("hranalyzer_races")
        .select("race_key, race_number")
        .eq("track_code", str(race.get("track_code", "")).strip())
        .eq("race_date", str(race.get("race_date", "")))
        .order("race_number")
        .execute()
        .data
    )

    navigation = {"prev_race_key": None, "next_race_key": None}
    current_index = next((idx for idx, sibling in enumerate(siblings) if sibling["race_key"] == race["race_key"]), -1)
    if current_index > 0:
        navigation["prev_race_key"] = siblings[current_index - 1]["race_key"]
    if 0 <= current_index < len(siblings) - 1:
        navigation["next_race_key"] = siblings[current_index + 1]["race_key"]

    current_status = derive_live_race_status(
        race["race_date"],
        race.get("post_time"),
        race["race_status"],
        (race.get("hranalyzer_tracks") or {}).get("timezone", "America/New_York"),
        has_results=any(entry.get("finish_position") in [1, 2, 3] for entry in entries),
    )

    return {
        "race": {
            "id": race["id"],
            "race_key": race["race_key"],
            "track_code": race["track_code"],
            "track_name": (race.get("hranalyzer_tracks") or {}).get("track_name", race["track_code"]),
            "location": (race.get("hranalyzer_tracks") or {}).get("location"),
            "race_number": race["race_number"],
            "race_date": race["race_date"],
            "post_time": race.get("post_time"),
            "post_time_display": format_to_12h(race.get("post_time")),
            "race_type": race.get("race_type"),
            "surface": race.get("surface"),
            "distance": race.get("distance"),
            "distance_feet": race.get("distance_feet"),
            "conditions": race.get("conditions"),
            "purse": race.get("purse"),
            "race_status": current_status,
            "data_source": race.get("data_source"),
            "final_time": race.get("final_time"),
            "fractional_times": race.get("fractional_times"),
            "equibase_chart_url": race.get("equibase_chart_url"),
            "equibase_pdf_url": race.get("equibase_pdf_url"),
        },
        "entries": entries,
        "exotic_payouts": exotic_payouts,
        "claims": claims,
        "navigation": navigation,
        "entry_count": len(entries),
    }


@mcp.tool()
def get_horses(search: str = "", limit: int = 50, page: int = 1, with_races: bool = False) -> dict:
    """Search horses and return aggregate stats with pagination."""
    supabase = get_supabase_client()
    limit = min(max(limit, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * limit

    query = supabase.table("hranalyzer_horses").select("*", count="exact")
    query = query.not_.like("horse_name", "$%").neq("horse_name", "-").neq("horse_name", "--").neq("horse_name", "N/A")
    if search:
        query = query.ilike("horse_name", f"%{search}%")
    response = query.order("horse_name").range(offset, offset + limit - 1).execute()

    horses_data = [horse for horse in response.data if is_valid_horse_name(horse.get("horse_name", ""))]
    horse_ids = [horse["id"] for horse in horses_data]
    stats_map = {}

    if horse_ids:
        entries_response = (
            supabase.table("hranalyzer_race_entries")
            .select("horse_id, finish_position, scratched, race:hranalyzer_races(race_date, track_code, race_status)")
            .in_("horse_id", horse_ids)
            .execute()
        )

        for entry in entries_response.data:
            horse_id = entry["horse_id"]
            stats_map.setdefault(
                horse_id,
                {
                    "total_races": 0,
                    "wins": 0,
                    "places": 0,
                    "shows": 0,
                    "last_race_date": None,
                    "last_track": None,
                },
            )

            if entry.get("scratched"):
                continue

            race = entry.get("race") or {}
            if race.get("race_status") != "completed":
                continue

            stats_map[horse_id]["total_races"] += 1
            if entry.get("finish_position") == 1:
                stats_map[horse_id]["wins"] += 1
            elif entry.get("finish_position") == 2:
                stats_map[horse_id]["places"] += 1
            elif entry.get("finish_position") == 3:
                stats_map[horse_id]["shows"] += 1

            race_date = race.get("race_date")
            if race_date and (
                not stats_map[horse_id]["last_race_date"] or race_date > stats_map[horse_id]["last_race_date"]
            ):
                stats_map[horse_id]["last_race_date"] = race_date
                stats_map[horse_id]["last_track"] = race.get("track_code")

    horses = []
    for horse in horses_data:
        stats = stats_map.get(
            horse["id"],
            {"total_races": 0, "wins": 0, "places": 0, "shows": 0, "last_race_date": None, "last_track": None},
        )
        if with_races and stats["total_races"] == 0:
            continue

        total_races = stats["total_races"]
        horses.append(
            {
                "id": horse["id"],
                "name": horse["horse_name"],
                "sire": horse.get("sire"),
                "dam": horse.get("dam"),
                "color": horse.get("color"),
                "sex": horse.get("sex"),
                "total_races": total_races,
                "wins": stats["wins"],
                "places": stats["places"],
                "shows": stats["shows"],
                "win_percentage": round((stats["wins"] / total_races) * 100, 1) if total_races > 0 else 0,
                "last_race_date": stats["last_race_date"],
                "last_track": stats["last_track"],
            }
        )

    total_count = response.count or 0
    return {
        "horses": horses,
        "count": len(horses),
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
    }


@mcp.tool()
def get_horse_profile(horse_id: str = "", horse_name: str = "") -> dict:
    """Get a horse profile by stable ID or by name with ambiguity handling."""
    supabase = get_supabase_client()
    horse = None

    if horse_id:
        response = supabase.table("hranalyzer_horses").select("*").eq("id", horse_id).single().execute()
        horse = response.data
        if not horse:
            return {"error": f"Horse not found: {horse_id}"}
    else:
        if not horse_name.strip():
            return {"error": "Provide either horse_id or horse_name"}

        exact_matches = (
            supabase.table("hranalyzer_horses")
            .select("id, horse_name, sire, dam, color, sex, foaling_year")
            .ilike("horse_name", horse_name.strip())
            .order("horse_name")
            .limit(10)
            .execute()
            .data
        )
        if len(exact_matches) == 1:
            horse = exact_matches[0]
        elif len(exact_matches) > 1:
            return {
                "error": "Multiple horses matched the provided horse_name. Retry with horse_id.",
                "matches": exact_matches,
                "count": len(exact_matches),
            }
        else:
            partial_matches = (
                supabase.table("hranalyzer_horses")
                .select("id, horse_name, sire, dam, color, sex, foaling_year")
                .ilike("horse_name", f"%{horse_name.strip()}%")
                .order("horse_name")
                .limit(10)
                .execute()
                .data
            )
            if len(partial_matches) == 1:
                horse = partial_matches[0]
            elif partial_matches:
                return {
                    "error": "Multiple horses matched the provided horse_name. Retry with horse_id.",
                    "matches": partial_matches,
                    "count": len(partial_matches),
                }
            else:
                return {"error": f"Horse not found: {horse_name}"}

    entries_response = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                id, program_number, finish_position, final_odds,
                win_payout, place_payout, show_payout, scratched, run_comments,
                race:hranalyzer_races(
                    race_key, race_date, race_number, track_code,
                    race_type, surface, distance, purse, race_status,
                    track:hranalyzer_tracks(track_name)
                ),
                jockey:hranalyzer_jockeys(jockey_name),
                trainer:hranalyzer_trainers(trainer_name)
            """
        )
        .eq("horse_id", horse["id"])
        .order("id", desc=True)
        .execute()
    )

    race_history = []
    stats = {"total": 0, "wins": 0, "places": 0, "shows": 0, "earnings": 0}
    for entry in entries_response.data:
        race = entry.get("race") or {}
        track = race.get("track") or {}
        jockey = entry.get("jockey") or {}
        trainer = entry.get("trainer") or {}

        race_history.append(
            {
                "race_key": race.get("race_key"),
                "race_date": race.get("race_date"),
                "track_code": race.get("track_code"),
                "track_name": track.get("track_name", race.get("track_code")),
                "race_number": race.get("race_number"),
                "race_type": race.get("race_type"),
                "surface": race.get("surface"),
                "distance": race.get("distance"),
                "purse": race.get("purse"),
                "program_number": entry.get("program_number"),
                "finish_position": entry.get("finish_position"),
                "final_odds": entry.get("final_odds"),
                "jockey_name": jockey.get("jockey_name", "N/A"),
                "trainer_name": trainer.get("trainer_name", "N/A"),
                "run_comments": entry.get("run_comments"),
                "scratched": entry.get("scratched", False),
                "race_status": race.get("race_status"),
            }
        )

        if race.get("race_status") == "completed" and not entry.get("scratched"):
            stats["total"] += 1
            if entry.get("finish_position") == 1:
                stats["wins"] += 1
                if entry.get("win_payout"):
                    stats["earnings"] += float(entry["win_payout"])
            elif entry.get("finish_position") == 2:
                stats["places"] += 1
                if entry.get("place_payout"):
                    stats["earnings"] += float(entry["place_payout"])
            elif entry.get("finish_position") == 3:
                stats["shows"] += 1
                if entry.get("show_payout"):
                    stats["earnings"] += float(entry["show_payout"])

    race_history.sort(key=lambda item: (item.get("race_date") or "", item.get("race_number") or 0), reverse=True)
    stats["win_percentage"] = round((stats["wins"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0

    return {
        "horse": {
            "id": horse["id"],
            "name": horse["horse_name"],
            "sire": horse.get("sire"),
            "dam": horse.get("dam"),
            "color": horse.get("color"),
            "sex": horse.get("sex"),
            "foaling_year": horse.get("foaling_year"),
        },
        "stats": stats,
        "race_history": race_history,
    }


@mcp.tool()
def get_scratches(
    view: str = "upcoming",
    page: int = 1,
    limit: int = 20,
    track: str = "All",
    start_date: str = "",
    end_date: str = "",
    race_number: int = 0,
) -> dict:
    """Get scratches with pagination and backend-parity fields."""
    supabase = get_supabase_client()
    today = date.today().isoformat()
    page = max(page, 1)
    limit = min(max(limit, 1), 200)
    requested_view = view or "upcoming"

    def run_query(applied_view):
        start = (page - 1) * limit
        end = start + limit - 1
        query = (
            supabase.table("hranalyzer_race_entries")
            .select(
                """
                    id, program_number, scratched, updated_at,
                    horse:hranalyzer_horses(horse_name),
                    trainer:hranalyzer_trainers(trainer_name),
                    race:hranalyzer_races!inner(
                        id, track_code, race_date, race_number, post_time, race_status,
                        track:hranalyzer_tracks(track_name)
                    )
                """,
                count="exact",
            )
            .eq("scratched", True)
        )

        query = _resolve_date_filtered_query(
            query,
            applied_view,
            today,
            start_date=start_date,
            end_date=end_date,
        )

        if track != "All":
            query = query.eq("race.track_code", track)
        if race_number:
            query = query.eq("race.race_number", race_number)

        if applied_view == "upcoming" and not (start_date or end_date):
            query = (
                query.order("race_date", foreign_table="race")
                .order("track_code", foreign_table="race")
                .order("race_number", foreign_table="race")
                .order("id")
            )
        else:
            query = (
                query.order("race_date", desc=True, foreign_table="race")
                .order("track_code", foreign_table="race")
                .order("race_number", foreign_table="race")
                .order("id")
            )

        return query.range(start, end).execute()

    applied_view = requested_view if requested_view in {"upcoming", "history", "all"} else "upcoming"
    response = run_query(applied_view)
    fallback_applied = False
    fallback_reason = ""

    if (
        applied_view == "upcoming"
        and not start_date
        and not end_date
        and not response.data
    ):
        applied_view = "all"
        response = run_query(applied_view)
        fallback_applied = True
        fallback_reason = "No upcoming scratches found; returning the most recent historical scratches instead."

    scratches = []
    for item in response.data or []:
        race = item.get("race") or {}
        track_info = race.get("track") or {}
        horse = item.get("horse") or {}
        trainer = item.get("trainer") or {}
        scratches.append(
            {
                "id": item["id"],
                "race_id": race.get("id"),
                "race_date": race.get("race_date"),
                "track_code": race.get("track_code"),
                "track_name": track_info.get("track_name", race.get("track_code")),
                "race_number": race.get("race_number"),
                "post_time": format_to_12h(race.get("post_time")),
                "program_number": item.get("program_number"),
                "horse_name": horse.get("horse_name", "Unknown"),
                "trainer_name": trainer.get("trainer_name", "Unknown"),
                "status": "Scratched",
                "updated_at": item.get("updated_at"),
            }
        )

    count = response.count if response.count is not None else len(scratches)
    return {
        "scratches": scratches,
        "count": count,
        "page": page,
        "limit": limit,
        "total_pages": (count + limit - 1) // limit if limit > 0 else 1,
        "meta": _build_feed_metadata(
            scratches,
            requested_view=requested_view,
            applied_view=applied_view,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
        ),
    }


@mcp.tool()
def get_changes(
    view: str = "upcoming",
    mode: str = "",
    page: int = 1,
    limit: int = 20,
    track: str = "All",
    start_date: str = "",
    end_date: str = "",
    race_number: int = 0,
) -> dict:
    """Get normalized, deduplicated changes feed matching backend semantics."""
    requested_view = mode or view or "upcoming"
    resolved_mode = requested_view if requested_view in {"upcoming", "history", "all"} else "upcoming"
    limit = min(max(limit, 1), 200)

    result = fetch_change_feed(
        mode=resolved_mode,
        page=page,
        limit=limit,
        track=track or "All",
        start_date=start_date,
        end_date=end_date,
        race_number=max(race_number, 0),
    )
    applied_view = resolved_mode
    fallback_applied = False
    fallback_reason = ""

    if (
        resolved_mode == "upcoming"
        and not start_date
        and not end_date
        and result.get("count", 0) == 0
    ):
        applied_view = "all"
        result = fetch_change_feed(
            mode=applied_view,
            page=page,
            limit=limit,
            track=track or "All",
            start_date=start_date,
            end_date=end_date,
            race_number=max(race_number, 0),
        )
        fallback_applied = True
        fallback_reason = "No upcoming changes found; returning the most recent historical changes instead."

    result["meta"] = _build_feed_metadata(
        result.get("changes", []),
        requested_view=requested_view,
        applied_view=applied_view,
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
    )
    return result


@mcp.tool()
def get_race_changes(race_id: str) -> dict:
    """Get all changes for a specific race ID."""
    supabase = get_supabase_client()
    all_changes = []
    race_snapshots = _fetch_race_snapshots(supabase, [race_id])

    scratch_response = (
        supabase.table("hranalyzer_race_entries")
        .select(
            """
                id, race_id, program_number, scratched, updated_at
            """
        )
        .eq("race_id", race_id)
        .eq("scratched", True)
        .execute()
    )
    scratch_rows = scratch_response.data or []
    scratch_entry_snapshots = _fetch_entry_snapshots(supabase, [item["id"] for item in scratch_rows if item.get("id")])
    for item in scratch_rows:
        all_changes.append(
            _build_change_record(
                item,
                scratch_entry_snapshots,
                race_snapshots,
                "entries",
                default_change_type="Scratch",
            )
        )

    try:
        changes_response = (
            supabase.table("hranalyzer_changes")
            .select(
                """
                    id,
                    entry_id,
                    race_id,
                    change_type,
                    description,
                    created_at
                """
            )
            .eq("race_id", race_id)
            .execute()
        )
        change_rows = changes_response.data or []
        change_entry_snapshots = _fetch_entry_snapshots(
            supabase,
            [item.get("entry_id") for item in change_rows if item.get("entry_id")],
        )
        for item in change_rows:
            all_changes.append(_build_change_record(item, change_entry_snapshots, race_snapshots, "changes"))
    except Exception:
        pass

    return {"changes": all_changes, "count": len(all_changes), "race_id": race_id}


@mcp.tool()
def get_claims(track: str = "", start_date: str = "", end_date: str = "", race_number: int = 0, limit: int = 100) -> dict:
    """Get claims with race context and IDs."""
    supabase = get_supabase_client()
    limit = min(max(limit, 1), 500)
    response = (
        supabase.table("hranalyzer_claims")
        .select("*, hranalyzer_races(race_key, track_code, race_date, race_number, hranalyzer_tracks(track_name))")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    claims = []
    for item in response.data:
        race = item.get("hranalyzer_races")
        if not race:
            continue

        track_info = race.get("hranalyzer_tracks")
        track_name = track_info.get("track_name") if track_info else race["track_code"]
        if track and race["track_code"] != track and track_name != track:
            continue
        if start_date and race["race_date"] < start_date:
            continue
        if end_date and race["race_date"] > end_date:
            continue
        if race_number and race["race_number"] != race_number:
            continue

        claims.append(
            {
                "id": item["id"],
                "race_key": race["race_key"],
                "race_date": race["race_date"],
                "track_code": race["track_code"],
                "track_name": track_name,
                "race_number": race["race_number"],
                "horse_name": item["horse_name"],
                "program_number": item.get("program_number"),
                "new_trainer": item["new_trainer_name"],
                "new_owner": item["new_owner_name"],
                "claim_price": item["claim_price"],
            }
        )

    return {"claims": claims, "count": len(claims)}


if __name__ == "__main__":
    print("Starting TrackData MCP Server on port 8001...")
    print("Connect your AI agent to: http://localhost:8001/mcp")
    mcp.run(transport="streamable-http")
