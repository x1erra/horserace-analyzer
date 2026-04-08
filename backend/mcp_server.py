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
from runtime_state import (
    get_database_health_snapshot,
    parse_iso,
    get_recent_boot_at,
    probe_database_health,
    summarize_freshness,
    utc_now,
)


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


def _is_scratch_feed_item(item):
    """Return True when a normalized change record represents a scratch."""
    return get_type_class(item) == "scratch"


def _format_scratch_feed_item(item):
    """Map a normalized scratch/change record into the scratches API shape."""
    description = item.get("description") or "Scratched"
    return {
        "id": item.get("entry_id") or item.get("id"),
        "change_id": item.get("id"),
        "race_id": item.get("race_id"),
        "race_key": item.get("race_key"),
        "race_date": item.get("race_date"),
        "track_code": item.get("track_code"),
        "track_name": item.get("track_name", item.get("track_code")),
        "race_number": item.get("race_number"),
        "post_time": format_to_12h(item.get("post_time")),
        "program_number": item.get("program_number"),
        "horse_name": item.get("horse_name", "Unknown"),
        "trainer_name": item.get("trainer_name", "Unknown"),
        "status": "Scratched",
        "description": description,
        "change_type": item.get("change_type") or "Scratch",
        "change_time": item.get("change_time"),
        "updated_at": item.get("change_time"),
    }


def _should_keep_change_item(item):
    """Filter out meaningless race-wide placeholders while preserving genuine race-wide events."""
    horse_name = item.get("horse_name")
    change_type = item.get("change_type") or ""
    description = item.get("description") or ""
    race_wide = horse_name in (None, "", "Race-wide", "Race-Wide")
    change_type_lower = change_type.lower()
    if not race_wide:
        return True
    if any(term in change_type_lower for term in ("scratch", "jockey", "weight", "equipment")):
        return False
    if "cancelled" in change_type_lower:
        return True
    if "post time" in change_type_lower:
        return True
    if description.strip():
        return True
    return False


def _normalize_change_list(all_changes, sort_desc=False):
    """Deduplicate and filter normalized change rows consistently across MCP surfaces."""
    normalized_map = {}
    for item in all_changes:
        if not _should_keep_change_item(item):
            continue

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

        winner = dict(winner)
        winner.pop("_source", None)
        final_list.append(winner)

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

    return final_list


def _track_matches(track_filter, race_track_code, race_track_name):
    if not track_filter:
        return True
    return track_filter in {race_track_code, race_track_name}


def _detect_pipeline_activity():
    """Probe for recent DB activity so freshness consumers can distinguish monitor lag from data outage."""
    supabase = get_supabase_client()
    today = date.today()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()
    tomorrow_str = (today + timedelta(days=1)).isoformat()
    day_after_str = (today + timedelta(days=2)).isoformat()

    signals = {
        "entries_data_present": False,
        "results_data_present": False,
        "scratches_data_present": False,
    }

    try:
        entries_probe = (
            supabase.table("hranalyzer_races")
            .select("id")
            .in_("race_date", [today_str, tomorrow_str, day_after_str])
            .limit(1)
            .execute()
        )
        signals["entries_data_present"] = bool(entries_probe.data)
    except Exception:
        pass

    try:
        results_probe = (
            supabase.table("hranalyzer_race_entries")
            .select("id, race:hranalyzer_races!inner(race_date)")
            .in_("finish_position", [1, 2, 3])
            .gte("race.race_date", yesterday_str)
            .lte("race.race_date", today_str)
            .limit(1)
            .execute()
        )
        signals["results_data_present"] = bool(results_probe.data)
    except Exception:
        pass

    try:
        scratches_probe = (
            supabase.table("hranalyzer_changes")
            .select("id, race:hranalyzer_races!inner(race_date)")
            .eq("change_type", "Scratch")
            .gte("race.race_date", yesterday_str)
            .lte("race.race_date", today_str)
            .limit(1)
            .execute()
        )
        signals["scratches_data_present"] = bool(scratches_probe.data)
    except Exception:
        pass

    if not signals["scratches_data_present"]:
        try:
            scratches_probe = (
                supabase.table("hranalyzer_race_entries")
                .select("id, race:hranalyzer_races!inner(race_date)")
                .eq("scratched", True)
                .gte("race.race_date", yesterday_str)
                .lte("race.race_date", today_str)
                .limit(1)
                .execute()
            )
            signals["scratches_data_present"] = bool(scratches_probe.data)
        except Exception:
            pass

    active_signals = [name.replace("_data_present", "") for name, active in signals.items() if active]
    return {
        **signals,
        "any_recent_data": any(signals.values()),
        "active_signals": active_signals,
    }


def _describe_crawler_status(crawl_name, item):
    if (
        crawl_name == "scratches"
        and item.get("observation_supporting_freshness")
        and item.get("last_observed_source")
    ):
        source = str(item.get("last_observed_source")).replace("_", " ")
        return (
            f"Recent scratch evidence was recorded via {source}, so scratch coverage appears current "
            "even without a recent dedicated late-changes success timestamp."
        )
    if item.get("within_startup_grace") and not item.get("last_success_at"):
        return "The service recently restarted and is still within startup grace, so a first successful timestamp may not exist yet."
    if item.get("stale"):
        threshold = item.get("threshold_minutes")
        if threshold:
            return f"No successful {crawl_name} crawl has been recorded within the expected {threshold}-minute window."
        return f"No recent successful {crawl_name} crawl has been recorded."
    if item.get("in_progress"):
        return "A crawl attempt is currently running or started recently."
    return "A recent successful crawl timestamp is recorded."


def _summarize_health_error(error_value):
    """Condense noisy upstream error payloads into operator-readable text."""
    if not error_value:
        return None

    text = str(error_value).strip()
    lowered = text.lower()

    if "error code 521" in lowered or "'code': 521" in lowered or "web server is down" in lowered:
        return "Supabase upstream returned Cloudflare 521 (web server down)."
    if "read operation timed out" in lowered:
        return "The database request timed out."
    if len(text) > 220:
        return f"{text[:217]}..."
    return text


def _classify_crawler_issue(item, public_status):
    """Separate active failures from historical residue for health reporting."""
    summarized = _summarize_health_error(item.get("last_error"))
    if not summarized:
        return None, None

    if public_status == "attention_needed" or (public_status == "running" and not item.get("last_success_at")):
        return summarized, None

    if item.get("last_success_at"):
        return None, {
            "message": summarized,
            "historical": True,
            "note": "This reflects the most recent prior failure, not the current crawler state.",
        }

    return summarized, None


def _status_label(status):
    return {
        "ok": "Healthy",
        "starting": "Starting Up",
        "running": "In Progress",
        "recovering": "Recovering",
        "attention_needed": "Attention Needed",
        "degraded": "Degraded",
        "unhealthy": "Unhealthy",
    }.get(status, status.replace("_", " ").title())


def _timestamp_state_for(item, public_status):
    if item.get("observation_supporting_freshness") and item.get("effective_last_success_at"):
        source = str(item.get("last_observed_source") or "alternate source").replace("_", " ")
        return {
            "state": "observed_via_alternate_source",
            "message": f"Fresh scratch activity was observed via {source} even though the dedicated crawler timestamp is older or missing.",
        }
    if item.get("last_success_at"):
        return {
            "state": "recorded",
            "message": "A successful crawl timestamp is recorded.",
        }
    if item.get("within_startup_grace"):
        return {
            "state": "pending_first_success",
            "message": "No successful timestamp is recorded yet because startup grace is still active after restart/deploy.",
        }
    if public_status == "recovering":
        return {
            "state": "catching_up",
            "message": "The database shows recent activity, and the freshness timestamp is still catching up.",
        }
    if item.get("in_progress"):
        return {
            "state": "attempt_running",
            "message": "A crawl attempt is running, so the next successful timestamp may not be written yet.",
        }
    return {
        "state": "missing",
        "message": "No successful crawl timestamp is recorded right now.",
    }


def _freshness_guidance(status, summary):
    if status == "ok":
        return {
            "risk_level": "none",
            "recommended_action": "No action needed.",
            "operator_summary": summary,
        }
    if status == "starting":
        return {
            "risk_level": "low",
            "recommended_action": "Wait for the first full crawler pass after redeploy/startup before treating this as a problem.",
            "operator_summary": summary,
        }
    if status == "recovering":
        return {
            "risk_level": "low",
            "recommended_action": (
                "Data is flowing, but crawler freshness timestamps are still catching up. Monitor scheduler logs and only escalate "
                "if this persists beyond one normal crawler loop."
            ),
            "operator_summary": summary,
        }
    if status == "degraded":
        return {
            "risk_level": "medium",
            "recommended_action": "Inspect open runtime alerts. Crawler freshness is current, so the issue is likely elsewhere.",
            "operator_summary": summary,
        }
    if status == "unhealthy":
        return {
            "risk_level": "high",
            "recommended_action": "Database connectivity is failing. Inspect Supabase connectivity, backend logs, and the database-connectivity alert immediately.",
            "operator_summary": summary,
        }
    return {
        "risk_level": "high",
        "recommended_action": "Investigate scheduler logs and /api/health immediately. One or more crawlers are genuinely stale.",
        "operator_summary": summary,
    }


def _db_snapshot_requires_live_probe(db_snapshot, scheduler_boot):
    if not db_snapshot.get("status"):
        return True

    checked_at = parse_iso(db_snapshot.get("checked_at"))
    if checked_at is None:
        return True

    if scheduler_boot and checked_at < scheduler_boot:
        return True

    if db_snapshot.get("status") == "disconnected":
        return True

    snapshot_ttl_minutes = int(os.getenv("DB_HEALTH_CACHE_TTL_MINUTES", "10"))
    age_minutes = (datetime.now(checked_at.tzinfo) - checked_at).total_seconds() / 60
    return age_minutes > snapshot_ttl_minutes


def _build_system_health_report():
    freshness, alerts = summarize_freshness()
    open_alerts = [alert for alert in alerts if alert.get("status") == "open"]
    db_snapshot = get_database_health_snapshot()
    scheduler_boot = get_recent_boot_at("scheduler")
    if _db_snapshot_requires_live_probe(db_snapshot, scheduler_boot):
        live_db = probe_database_health()
        db = {
            **live_db,
            "checked_at": utc_now(),
        }
    else:
        db = {
            "status": db_snapshot.get("status", "unknown"),
            "label": db_snapshot.get("label", "Unknown"),
            "message": db_snapshot.get("message", "No recent database health check is recorded."),
            "error": db_snapshot.get("error"),
            "checked_at": db_snapshot.get("checked_at"),
        }

    pipeline_activity = {
        "entries_data_present": bool(freshness.get("entries", {}).get("last_success_at")),
        "results_data_present": bool(freshness.get("results", {}).get("last_success_at")),
        "scratches_data_present": bool(
            freshness.get("scratches", {}).get("effective_last_success_at")
            or freshness.get("scratches", {}).get("last_success_at")
        ),
    }
    pipeline_activity["active_signals"] = [
        name.replace("_data_present", "")
        for name, active in pipeline_activity.items()
        if name.endswith("_data_present") and active
    ]
    pipeline_activity["any_recent_data"] = any(
        pipeline_activity[name]
        for name in ("entries_data_present", "results_data_present", "scratches_data_present")
    )

    crawler = {}
    healthy_crawlers = []
    starting_crawlers = []
    running_crawlers = []
    recovering_crawlers = []
    attention_needed_crawlers = []

    for crawl_name, item in freshness.items():
        signal_key = f"{crawl_name}_data_present"
        public_status = "ok"
        if item.get("within_startup_grace") and not item.get("last_success_at"):
            public_status = "starting"
            starting_crawlers.append(crawl_name)
        elif item.get("stale") and pipeline_activity.get(signal_key):
            public_status = "recovering"
            recovering_crawlers.append(crawl_name)
        elif item.get("stale"):
            public_status = "attention_needed"
            attention_needed_crawlers.append(crawl_name)
        elif item.get("in_progress"):
            public_status = "running"
            running_crawlers.append(crawl_name)
        else:
            healthy_crawlers.append(crawl_name)

        current_issue, recent_incident = _classify_crawler_issue(item, public_status)

        crawler[crawl_name] = {
            "last_attempt_at": item.get("last_attempt_at"),
            "last_success_at": item.get("effective_last_success_at") or item.get("last_success_at"),
            "age_minutes": item.get("age_minutes"),
            "threshold_minutes": item.get("threshold_minutes"),
            "status": public_status,
            "status_label": _status_label(public_status),
            "reason": _describe_crawler_status(crawl_name, item),
            "timestamps": {
                "last_success_at": item.get("effective_last_success_at") or item.get("last_success_at"),
                "last_attempt_at": item.get("last_attempt_at"),
                **_timestamp_state_for(item, public_status),
            },
        }
        if crawl_name == "scratches":
            crawler[crawl_name]["evidence"] = {
                "effective_last_success_at": item.get("effective_last_success_at"),
                "last_dedicated_success_at": item.get("last_success_at"),
                "last_observed_at": item.get("last_observed_at"),
                "last_observed_source": item.get("last_observed_source"),
                "using_observed_activity": bool(item.get("observation_supporting_freshness")),
            }
        if current_issue:
            crawler[crawl_name]["current_issue"] = current_issue
        if recent_incident:
            crawler[crawl_name]["recent_incident"] = recent_incident
        if public_status == "attention_needed" and item.get("last_details"):
            crawler[crawl_name]["last_details"] = item.get("last_details")

    if db["status"] == "disconnected":
        status = "unhealthy"
        summary = "The database connection check failed."
    elif db["status"] == "unknown":
        status = "starting"
        summary = "Database health has not been checked yet after the latest restart."
    elif attention_needed_crawlers:
        status = "attention_needed"
        summary = f"One or more crawlers need attention: {', '.join(attention_needed_crawlers)}."
    elif starting_crawlers:
        status = "starting"
        summary = "The services recently restarted and crawler timestamps are still being established."
    elif recovering_crawlers:
        status = "recovering"
        summary = (
            "Recent database activity is present, and one or more freshness timestamps are still catching up."
        )
    elif open_alerts:
        status = "degraded"
        summary = f"There are {len(open_alerts)} open runtime alert(s), but crawler freshness is otherwise current."
    else:
        status = "ok"
        if running_crawlers:
            summary = f"System is healthy. Active crawler work is in progress: {', '.join(running_crawlers)}."
        else:
            summary = "System is healthy. Database connectivity and crawler freshness look good."

    guidance = _freshness_guidance(status, summary)

    return {
        "status": status,
        "status_label": _status_label(status),
        "summary": summary,
        "recommended_action": guidance["recommended_action"],
        "risk_level": guidance["risk_level"],
        "operator_summary": guidance["operator_summary"],
        "checked_at": utc_now(),
        "version": "1.0.3",
        "runtime": {
            "scheduler_boot_at": scheduler_boot.isoformat().replace("+00:00", "Z") if scheduler_boot else None,
        },
        "database": db,
        "database_status": db["status"],
        "crawlers": crawler,
        "crawler": crawler,
        "crawler_summary": {
            "healthy": healthy_crawlers,
            "starting": starting_crawlers,
            "running": running_crawlers,
            "recovering": recovering_crawlers,
            "attention_needed": attention_needed_crawlers,
        },
        "open_alerts": open_alerts,
        "alerts": open_alerts,
        "open_alert_count": len(open_alerts),
        "alert_count": len(open_alerts),
        "pipeline_activity": pipeline_activity,
        "how_to_read": (
            "Trust status first. Use ok, starting, recovering, attention_needed, degraded, and unhealthy as the only top-level states. "
            "Per-crawler timestamps explain whether a timestamp is recorded, still pending after restart, delayed behind live data, or missing."
        ),
        "legacy_compatibility": {
            "all_crawlers_fresh": not attention_needed_crawlers and not starting_crawlers and not recovering_crawlers,
            "attention_needed_crawlers": attention_needed_crawlers,
            "starting_crawlers": starting_crawlers,
            "running_crawlers": running_crawlers,
            "recovering_crawlers": recovering_crawlers,
            "monitor_delay_crawlers": recovering_crawlers,
        },
    }


def _fetch_normalized_change_batch(
    supabase,
    mode,
    today,
    track,
    start_date,
    end_date,
    race_number,
    change_range=None,
    scratch_range=None,
):
    """Fetch and normalize a bounded change batch so history mode can page incrementally."""
    all_changes = []
    entries_with_detailed_scratches = set()
    change_rows = []

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
        if change_range is not None:
            changes_query = changes_query.order("created_at", desc=True).range(change_range[0], change_range[1])

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
        change_rows = []

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
    if scratch_range is not None:
        scratch_query = scratch_query.order("updated_at", desc=True).range(scratch_range[0], scratch_range[1])

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

    normalized = _normalize_change_list(all_changes, sort_desc=mode in {"history", "all"} or bool(start_date or end_date))
    normalized = [
        item
        for item in normalized
        if item.get("change_type") != "Wagering"
        and "wagering" not in (item.get("description") or "").lower()
    ]

    return {
        "changes": normalized,
        "raw_change_count": len(change_rows),
        "raw_scratch_count": len(scratch_rows),
    }


def _is_race_wide_change(item):
    """Return True when a normalized change row applies to the full race, not a single horse."""
    horse_name = (item.get("horse_name") or "").strip().lower()
    if horse_name in {"race-wide", "race wide", "race-wide change"}:
        return True
    return not item.get("entry_id")


def _apply_change_visibility(changes, include_race_wide):
    """Optionally hide race-wide rows for consumers that want only horse-specific changes."""
    if include_race_wide:
        return list(changes)
    return [item for item in changes if not _is_race_wide_change(item)]


def fetch_change_feed(
    mode="upcoming",
    page=1,
    limit=20,
    track="All",
    start_date="",
    end_date="",
    race_number=0,
    include_race_wide=True,
):
    """Mirror backend change merge and dedupe logic for MCP consumers."""
    supabase = get_supabase_client()
    today = date.today().isoformat()
    start = max(page - 1, 0) * limit
    end = start + limit
    history_like = mode in {"history", "all"} or bool(start_date or end_date)

    if not history_like:
        batch = _fetch_normalized_change_batch(
            supabase,
            mode,
            today,
            track,
            start_date,
            end_date,
            race_number,
        )
        final_list = _apply_change_visibility(batch["changes"], include_race_wide)
        return {
            "changes": final_list[start:end],
            "count": len(final_list),
            "page": page,
            "limit": limit,
            "total_pages": (len(final_list) + limit - 1) // limit if limit > 0 else 1,
            "has_more": page * limit < len(final_list),
        }

    chunk_size = max(limit * 4, 100)
    offset = 0
    collected = []
    has_more = False
    exhausted = False

    while True:
        batch = _fetch_normalized_change_batch(
            supabase,
            mode,
            today,
            track,
            start_date,
            end_date,
            race_number,
            change_range=(offset, offset + chunk_size - 1),
            scratch_range=(offset, offset + chunk_size - 1),
        )

        collected.extend(batch["changes"])
        final_list = _normalize_change_list(collected, sort_desc=True)
        final_list = [
            item
            for item in final_list
            if item.get("change_type") != "Wagering"
            and "wagering" not in (item.get("description") or "").lower()
        ]
        final_list = _apply_change_visibility(final_list, include_race_wide)

        exhausted = batch["raw_change_count"] < chunk_size and batch["raw_scratch_count"] < chunk_size
        if len(final_list) > end:
            has_more = True
            break
        if exhausted:
            has_more = False
            break
        offset += chunk_size

    return {
        "changes": final_list[start:end],
        "count": len(final_list),
        "page": page,
        "limit": limit,
        "total_pages": (len(final_list) + limit - 1) // limit if exhausted and limit > 0 else max(page + (1 if has_more else 0), 1),
        "has_more": has_more,
    }


def fetch_scratch_feed(mode="upcoming", page=1, limit=20, track="All", start_date="", end_date="", race_number=0):
    """Return scratches using the normalized change feed so late-change scratches are never invisible."""
    change_feed = fetch_change_feed(
        mode=mode,
        page=1,
        limit=10000,
        track=track,
        start_date=start_date,
        end_date=end_date,
        race_number=race_number,
        include_race_wide=False,
    )
    scratch_items = [_format_scratch_feed_item(item) for item in change_feed.get("changes", []) if _is_scratch_feed_item(item)]
    start = max(page - 1, 0) * limit
    end = start + limit
    paginated = scratch_items[start:end]
    return {
        "scratches": paginated,
        "count": len(scratch_items),
        "page": page,
        "limit": limit,
        "total_pages": (len(scratch_items) + limit - 1) // limit if limit > 0 else 1,
    }


@mcp.tool()
def get_health() -> dict:
    """Get the full one-stop system health report."""
    return _build_system_health_report()


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
    """Backward-compatible alias for the one-stop system health report."""
    report = _build_system_health_report()
    report["tool_alias"] = "get_feed_freshness"
    report["canonical_tool"] = "get_health"
    report["deprecated"] = True
    report["alias_note"] = "Use get_health as the canonical health endpoint. get_feed_freshness returns the same report for backward compatibility."
    return report


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
            "entries": entries,
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
            "horse_name": horse["horse_name"],
            "sire": horse.get("sire"),
            "dam": horse.get("dam"),
            "color": horse.get("color"),
            "sex": horse.get("sex"),
            "foaling_year": horse.get("foaling_year"),
        },
        "stats": stats,
        "race_history": race_history,
        "recent_races": race_history,
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
    """Get scratches with pagination, using the normalized change feed plus scratched entries."""
    page = max(page, 1)
    limit = min(max(limit, 1), 200)
    requested_view = view or "upcoming"

    applied_view = requested_view if requested_view in {"upcoming", "history", "all"} else "upcoming"
    result = fetch_scratch_feed(
        mode=applied_view,
        page=page,
        limit=limit,
        track=track or "All",
        start_date=start_date,
        end_date=end_date,
        race_number=max(race_number, 0),
    )
    fallback_applied = False
    fallback_reason = ""

    if (
        applied_view == "upcoming"
        and not start_date
        and not end_date
        and result.get("count", 0) == 0
    ):
        applied_view = "all"
        result = fetch_scratch_feed(
            mode=applied_view,
            page=page,
            limit=limit,
            track=track or "All",
            start_date=start_date,
            end_date=end_date,
            race_number=max(race_number, 0),
        )
        fallback_applied = True
        fallback_reason = "No upcoming scratches found; returning the most recent historical scratches instead."

    scratches = result.get("scratches", [])
    count = result.get("count", len(scratches))
    return {
        "scratches": scratches,
        "count": count,
        "page": result.get("page", page),
        "limit": result.get("limit", limit),
        "total_pages": result.get("total_pages", (count + limit - 1) // limit if limit > 0 else 1),
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
    include_race_wide: bool = False,
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
        include_race_wide=include_race_wide,
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
            include_race_wide=include_race_wide,
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
    result["meta"]["include_race_wide"] = include_race_wide
    result["meta"]["race_wide_hidden"] = not include_race_wide
    return result


@mcp.tool()
def get_race_changes(race_id: str, include_race_wide: bool = False) -> dict:
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

    normalized = _normalize_change_list(all_changes, sort_desc=True)
    visible_changes = _apply_change_visibility(normalized, include_race_wide)
    return {
        "changes": visible_changes,
        "count": len(visible_changes),
        "race_id": race_id,
        "meta": {
            "include_race_wide": include_race_wide,
            "race_wide_hidden": not include_race_wide,
        },
    }


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
    missing_claimant_details = 0
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

        new_trainer = item.get("new_trainer_name")
        new_owner = item.get("new_owner_name")
        claimant_details_complete = bool((new_trainer or "").strip() and (new_owner or "").strip())
        if not claimant_details_complete:
            missing_claimant_details += 1

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
                "new_trainer": new_trainer,
                "new_owner": new_owner,
                "claimant_details_complete": claimant_details_complete,
                "claim_price": item["claim_price"],
            }
        )

    return {
        "claims": claims,
        "count": len(claims),
        "meta": {
            "claims_with_complete_details": len(claims) - missing_claimant_details,
            "missing_claimant_details": missing_claimant_details,
            "claimant_detail_coverage_pct": round(((len(claims) - missing_claimant_details) / len(claims)) * 100, 1) if claims else 100.0,
            "all_claimant_details_complete": missing_claimant_details == 0,
        },
    }


if __name__ == "__main__":
    print("Starting TrackData MCP Server on port 8001...")
    print("Connect your AI agent to: http://localhost:8001/mcp")
    mcp.run(transport="streamable-http")
