import json
import logging
import os
import tempfile
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests


STATE_VERSION = 1
DEFAULT_ALERT_HISTORY_LIMIT = 50
DEFAULT_SUMMARY_FAILURE_THRESHOLD = 3
DEFAULT_SUMMARY_FAILURE_WINDOW_MINUTES = 15
DEFAULT_ENTRIES_STALE_MINUTES = 300
DEFAULT_RESULTS_STALE_MINUTES = 30
DEFAULT_SCRATCHES_STALE_MINUTES = 20
DEFAULT_ACTIVE_ATTEMPT_GRACE_MINUTES = 20
DEFAULT_CRAWL_ALERT_CONFIRM_EVALUATIONS = 3
ALERT_DISPATCH_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _discover_runtime_dir():
    explicit = os.getenv("RUNTIME_STATE_DIR")
    if explicit:
        return Path(explicit)

    log_dir = os.getenv("LOG_DIR")
    if log_dir:
        return Path(log_dir)

    candidates = [
        Path("/app/logs"),
        Path("/var/log"),
        Path(__file__).resolve().parent.parent / "logs",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    fallback = Path(tempfile.gettempdir()) / "horserace-analyzer-runtime"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


RUNTIME_DIR = _discover_runtime_dir()
STATE_FILE = RUNTIME_DIR / "runtime_state.json"


def _empty_state():
    return {
        "version": STATE_VERSION,
        "service_boots": {},
        "crawl_status": {},
        "dashboard_summaries": {},
        "summary_failures": {},
        "alerts": [],
    }


def load_state():
    if not STATE_FILE.exists():
        return _empty_state()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
            if isinstance(raw, dict):
                state = _empty_state()
                state.update(raw)
                return state
    except Exception:
        pass
    return _empty_state()


def save_state(state):
    state = deepcopy(state)
    state["version"] = STATE_VERSION
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    tmp_path.replace(STATE_FILE)


def update_state(mutator):
    state = load_state()
    mutator(state)
    save_state(state)


def snapshot_dashboard_summary(target_date, payload):
    target_date = str(target_date)

    def mutator(state):
        state["dashboard_summaries"][target_date] = {
            "captured_at": utc_now(),
            "payload": payload,
        }

    update_state(mutator)


def get_dashboard_summary_snapshot(target_date):
    state = load_state()
    snapshot = state.get("dashboard_summaries", {}).get(str(target_date))
    return snapshot if isinstance(snapshot, dict) else None


def record_dashboard_summary_failure(target_date, message):
    target_date = str(target_date)
    now = utc_now()
    threshold = int(os.getenv("SUMMARY_FAILURE_THRESHOLD", DEFAULT_SUMMARY_FAILURE_THRESHOLD))
    window_minutes = int(os.getenv("SUMMARY_FAILURE_WINDOW_MINUTES", DEFAULT_SUMMARY_FAILURE_WINDOW_MINUTES))

    def mutator(state):
        bucket = state["summary_failures"].setdefault(target_date, {"failures": []})
        failures = bucket["failures"]
        failures.append({"at": now, "message": message})

        cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
        trimmed = []
        for failure in failures:
            failure_dt = parse_iso(failure.get("at"))
            if not failure_dt:
                continue
            comparison_now = cutoff.replace(tzinfo=failure_dt.tzinfo)
            if failure_dt >= comparison_now:
                trimmed.append(failure)
        bucket["failures"] = trimmed

        if len(bucket["failures"]) >= threshold:
            upsert_alert(
                state,
                key=f"dashboard-summary-failures:{target_date}",
                severity="critical",
                message=f"Dashboard summary failed repeatedly for {target_date}",
                details={
                    "target_date": target_date,
                    "failure_count": len(bucket["failures"]),
                    "latest_error": message,
                },
            )

    update_state(mutator)
    dispatch_pending_alert_notifications()


def clear_dashboard_summary_failures(target_date):
    target_date = str(target_date)

    def mutator(state):
        state.get("summary_failures", {}).pop(target_date, None)
        resolve_alert(state, f"dashboard-summary-failures:{target_date}")

    update_state(mutator)
    dispatch_pending_alert_notifications()


def upsert_alert(state, key, severity, message, details=None):
    now = utc_now()
    alerts = state.setdefault("alerts", [])
    for alert in alerts:
        if alert.get("key") == key:
            was_open = alert.get("status") == "open"
            alert["status"] = "open"
            alert["severity"] = severity
            alert["message"] = message
            alert["details"] = details or {}
            alert["last_seen_at"] = now
            alert["count"] = int(alert.get("count", 1)) + 1
            if not was_open:
                alert["notified_open"] = False
                alert["notified_resolved"] = False
                alert.pop("resolved_at", None)
            break
    else:
        alerts.append({
            "key": key,
            "severity": severity,
            "message": message,
            "details": details or {},
            "status": "open",
            "first_seen_at": now,
            "last_seen_at": now,
            "count": 1,
            "notified_open": False,
            "notified_resolved": False,
        })

    limit = int(os.getenv("ALERT_HISTORY_LIMIT", DEFAULT_ALERT_HISTORY_LIMIT))
    if len(alerts) > limit:
        alerts[:] = alerts[-limit:]


def resolve_alert(state, key, details=None, notify=True):
    for alert in state.get("alerts", []):
        if alert.get("key") == key:
            if details is not None:
                alert["details"] = details
            if alert.get("status") != "resolved":
                alert["status"] = "resolved"
                alert["resolved_at"] = utc_now()
                alert["notified_resolved"] = not notify
            break


def _get_alert_webhook_url():
    return os.getenv("ALERT_WEBHOOK_URL")


def _alert_color(severity):
    return {
        "critical": 15158332,
        "warning": 16753920,
        "info": 3447003,
    }.get(severity, 9807270)


def _format_alert_detail_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key, nested_value in value.items():
            formatted = _format_alert_detail_value(nested_value)
            if formatted is not None:
                parts.append(f"{key}={formatted}")
        return ", ".join(parts) if parts else None
    if isinstance(value, list):
        parts = [_format_alert_detail_value(item) for item in value]
        parts = [item for item in parts if item is not None]
        return ", ".join(parts) if parts else None
    return str(value)


def _humanize_alert_detail_key(key):
    labels = {
        "age_minutes": "Age (minutes)",
        "changes_processed": "Changes Processed",
        "last_attempt_at": "Last Attempt",
        "last_error": "Error",
        "last_success_at": "Last Success",
        "phase": "Phase",
        "races_found": "Races Found",
        "startup_grace_reason": "Startup Grace",
        "target_date": "Target Date",
        "threshold_minutes": "Alert Threshold (minutes)",
        "today_races_found": "Today's Races Found",
        "tracks_checked": "Tracks Checked",
    }
    return labels.get(key, key.replace("_", " ").title())


def _normalize_alert_details(details):
    normalized = dict(details or {})
    nested = normalized.pop("last_details", None)
    if isinstance(nested, dict):
        for key, value in nested.items():
            normalized.setdefault(key, value)
    return normalized


def _describe_alert_reason(alert, details, is_resolved):
    key = alert.get("key", "")
    threshold = details.get("threshold_minutes")
    last_error = details.get("last_error")

    if key.startswith("crawl-stale:"):
        crawl_name = key.split(":", 1)[1].replace("-", " ").title()
        if is_resolved:
            return f"A successful {crawl_name.lower()} crawl was recorded."
        if threshold:
            reason = f"No successful {crawl_name.lower()} crawl has been recorded in the last {threshold} minutes."
        else:
            reason = f"No recent successful {crawl_name.lower()} crawl has been recorded."
        if last_error:
            reason += f" Latest error: {last_error}"
        return reason

    if key.startswith("dashboard-summary-failures:"):
        failure_count = details.get("failure_count")
        target_date = details.get("target_date")
        latest_error = details.get("latest_error")
        reason = "The dashboard summary endpoint has failed repeatedly"
        if target_date:
            reason += f" for {target_date}"
        if failure_count:
            reason += f" ({failure_count} times)"
        reason += "."
        if latest_error:
            reason += f" Latest error: {latest_error}"
        return reason

    if key == "dashboard-zero-races-during-racing-hours":
        return "The dashboard summary returned zero races during active racing hours."

    if is_resolved:
        return "The underlying issue is no longer active."

    return None


def _build_alert_payload(alert):
    severity = (alert.get("severity") or "warning").upper()
    status = (alert.get("status") or "open").upper()
    details = _normalize_alert_details(alert.get("details") or {})
    is_resolved = status == "RESOLVED"

    headline = alert.get("message", alert.get("key", "Unknown alert"))
    if is_resolved and details.get("last_success_at"):
        content = f"TrackData alert resolved: {headline}"
    elif is_resolved and details.get("within_startup_grace"):
        content = f"TrackData startup grace: {headline}"
    else:
        content = f"TrackData alert {status.lower()}: {headline}"

    preferred_detail_order = [
        "target_date",
        "phase",
        "last_success_at",
        "last_attempt_at",
        "age_minutes",
        "tracks_checked",
        "races_found",
        "today_races_found",
        "changes_processed",
        "last_error",
    ]

    detail_lines = []
    seen = set()
    for key in preferred_detail_order + list(details.keys()):
        if key in seen or key not in details:
            continue
        seen.add(key)
        value = details.get(key)
        if key in {"in_progress", "within_startup_grace"} and not value:
            continue
        if key in {"stale", "count", "threshold_minutes", "startup_grace_reason"}:
            continue
        formatted = _format_alert_detail_value(details.get(key))
        if formatted is not None:
            detail_lines.append(f"**{_humanize_alert_detail_key(key)}:** {formatted}")

    reason = _describe_alert_reason(alert, details, is_resolved)
    description_parts = [f"**Issue:** {headline}"]
    if reason:
        description_parts.append(f"**Why:** {reason}")
    if detail_lines:
        description_parts.append("\n".join(detail_lines))
    description = "\n\n".join(description_parts) if description_parts else "No additional details."

    return {
        "content": content,
        "embeds": [
            {
                "title": headline,
                "description": description[:4000],
                "color": _alert_color(alert.get("severity")),
                "fields": [
                    {"name": "Severity", "value": severity, "inline": True},
                    {"name": "Status", "value": status, "inline": True},
                ],
                "footer": {"text": "TrackData runtime alert"},
                "timestamp": utc_now().replace("Z", "+00:00"),
            }
        ],
    }


def dispatch_pending_alert_notifications():
    webhook_url = _get_alert_webhook_url()
    if not webhook_url:
        return

    state = load_state()
    alerts = state.get("alerts", [])
    changed = False

    for alert in alerts:
        should_send_open = alert.get("status") == "open" and not alert.get("notified_open")
        should_send_resolved = alert.get("status") == "resolved" and not alert.get("notified_resolved")
        if not should_send_open and not should_send_resolved:
            continue

        payload = _build_alert_payload(alert)
        try:
            response = requests.post(webhook_url, json=payload, timeout=ALERT_DISPATCH_TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to dispatch alert %s to Discord webhook: %s", alert.get("key"), exc)
            continue

        if should_send_open:
            alert["notified_open"] = True
        if should_send_resolved:
            alert["notified_resolved"] = True
        changed = True

    if changed:
        save_state(state)


def raise_alert(key, severity, message, details=None):
    update_state(lambda state: upsert_alert(state, key, severity, message, details))
    dispatch_pending_alert_notifications()


def clear_alert(key):
    update_state(lambda state: resolve_alert(state, key))
    dispatch_pending_alert_notifications()


def mark_runtime_boot(service_name):
    now = utc_now()

    def mutator(state):
        state.setdefault("service_boots", {})[service_name] = now

    update_state(mutator)


def get_recent_boot_at(service_name):
    state = load_state()
    value = state.get("service_boots", {}).get(service_name)
    return parse_iso(value)


def mark_crawl_attempt(crawl_type, details=None):
    now = utc_now()
    details = details or {}

    def mutator(state):
        status = state.setdefault("crawl_status", {}).setdefault(crawl_type, {})
        status["last_attempt_at"] = now
        status["last_details"] = details

    update_state(mutator)


def update_crawl_status(crawl_type, success, details=None):
    now = utc_now()
    details = details or {}

    def mutator(state):
        status = state.setdefault("crawl_status", {}).setdefault(crawl_type, {})
        status["last_attempt_at"] = now
        status["last_details"] = details
        if success:
            status["last_success_at"] = now
            status["last_success_details"] = details
            status["last_error"] = None
            resolve_alert(
                state,
                f"crawl-stale:{crawl_type}",
                details={
                    "last_attempt_at": now,
                    "last_success_at": now,
                    "last_details": details,
                    "last_error": None,
                    "age_minutes": 0,
                    "stale": False,
                },
            )
        else:
            status["last_error"] = details.get("error") or "Unknown crawl failure"

    update_state(mutator)
    dispatch_pending_alert_notifications()


def summarize_freshness(now=None):
    state = load_state()
    now_dt = now or datetime.now(UTC)
    startup_grace_minutes = int(os.getenv("ALERT_STARTUP_GRACE_MINUTES", "15"))
    active_attempt_grace_minutes = int(
        os.getenv("ACTIVE_CRAWL_GRACE_MINUTES", str(DEFAULT_ACTIVE_ATTEMPT_GRACE_MINUTES))
    )
    scheduler_boot_at = parse_iso(state.get("service_boots", {}).get("scheduler"))
    within_startup_grace = False
    if scheduler_boot_at:
        boot_age = now_dt.replace(tzinfo=scheduler_boot_at.tzinfo) - scheduler_boot_at
        within_startup_grace = boot_age <= timedelta(minutes=startup_grace_minutes)
    thresholds = {
        "entries": int(os.getenv("ENTRIES_STALE_MINUTES", str(DEFAULT_ENTRIES_STALE_MINUTES))),
        "results": int(os.getenv("RESULTS_STALE_MINUTES", str(DEFAULT_RESULTS_STALE_MINUTES))),
        "scratches": int(os.getenv("SCRATCHES_STALE_MINUTES", str(DEFAULT_SCRATCHES_STALE_MINUTES))),
    }

    freshness = {}
    for crawl_type, threshold_minutes in thresholds.items():
        status = state.get("crawl_status", {}).get(crawl_type, {})
        last_success_at = parse_iso(status.get("last_success_at"))
        last_attempt_at = parse_iso(status.get("last_attempt_at"))
        age_minutes = None
        stale = True
        if last_success_at:
            age_delta = now_dt.replace(tzinfo=last_success_at.tzinfo) - last_success_at
            age_minutes = int(age_delta.total_seconds() // 60)
            stale = age_minutes > threshold_minutes
        elif within_startup_grace:
            stale = False
        in_progress = False
        if last_attempt_at:
            if not last_success_at or last_attempt_at > last_success_at:
                attempt_age = now_dt.replace(tzinfo=last_attempt_at.tzinfo) - last_attempt_at
                in_progress = attempt_age <= timedelta(minutes=active_attempt_grace_minutes)
                if in_progress:
                    stale = False

        freshness[crawl_type] = {
            "last_attempt_at": status.get("last_attempt_at"),
            "last_success_at": status.get("last_success_at"),
            "last_error": status.get("last_error"),
            "last_details": status.get("last_details"),
            "age_minutes": age_minutes,
            "stale": stale,
            "threshold_minutes": threshold_minutes,
            "within_startup_grace": within_startup_grace,
            "in_progress": in_progress,
        }
        if within_startup_grace and not status.get("last_success_at"):
            freshness[crawl_type]["startup_grace_reason"] = (
                f"Suppressing stale alerts for {startup_grace_minutes} minutes after deploy/startup"
            )

    return freshness, state.get("alerts", [])


def _reset_stale_tracking(status):
    status.pop("stale_since", None)
    status.pop("stale_evaluations", None)


def evaluate_runtime_alerts(today_summary_total=None, during_racing_hours=False, include_crawl_alerts=True):
    freshness, _alerts = summarize_freshness()
    required_stale_evaluations = int(
        os.getenv("CRAWL_ALERT_CONFIRM_EVALUATIONS", str(DEFAULT_CRAWL_ALERT_CONFIRM_EVALUATIONS))
    )

    def mutator(state):
        if include_crawl_alerts:
            for crawl_type, item in freshness.items():
                key = f"crawl-stale:{crawl_type}"
                status = state.setdefault("crawl_status", {}).setdefault(crawl_type, {})
                if item["stale"]:
                    stale_evaluations = int(status.get("stale_evaluations", 0)) + 1
                    status["stale_evaluations"] = stale_evaluations
                    status.setdefault("stale_since", utc_now())

                    if stale_evaluations >= required_stale_evaluations:
                        upsert_alert(
                            state,
                            key=key,
                            severity="warning" if crawl_type == "entries" else "critical",
                            message=f"{crawl_type.title()} crawl is stale",
                            details={
                                **item,
                                "stale_since": status.get("stale_since"),
                                "stale_evaluations": stale_evaluations,
                            },
                        )
                else:
                    _reset_stale_tracking(status)
                    suppress_resolved_notification = item.get("within_startup_grace") and not item.get("last_success_at")
                    resolve_alert(state, key, details=item, notify=not suppress_resolved_notification)

        if during_racing_hours and today_summary_total == 0:
            upsert_alert(
                state,
                key="dashboard-zero-races-during-racing-hours",
                severity="critical",
                message="Dashboard summary returned zero races during racing hours",
                details={"date": str(date.today())},
            )
        elif today_summary_total is not None:
            resolve_alert(state, "dashboard-zero-races-during-racing-hours")

    update_state(mutator)
    dispatch_pending_alert_notifications()
