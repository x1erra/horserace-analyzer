# TrackData MCP Tools

This document describes the full TrackData MCP tool surface and how to interpret each tool without guessing.

The TrackData MCP server is read-only and runs at:

```text
http://<host>:8001/mcp
```

## Read This First

### Preferred health tool

Use `get_health()` as the primary one-stop system report.

It combines:
- database connectivity
- crawler freshness state
- open runtime alerts
- recent pipeline activity
- clear operator guidance

`get_feed_freshness()` is a backward-compatible alias to the same core report. It exists so older agents keep working, but new agents should prefer `get_health()`.

### Top-level health states

Do not invent your own interpretation from raw timestamps alone.

Trust `status` first:
- `ok`: system health looks good
- `starting`: the stack recently restarted and timestamps are still being established
- `recovering`: live data is present in the database, and freshness timestamps are still catching up
- `attention_needed`: one or more crawlers truly need investigation
- `degraded`: crawler freshness is okay, but another runtime alert is open
- `unhealthy`: the database or core service health check failed

Also read:
- `status_label`
- `summary`
- `recommended_action`
- `risk_level`

### Per-crawler states

Each crawler under `crawlers.<name>.status` will be one of:
- `ok`
- `starting`
- `running`
- `recovering`
- `attention_needed`

Each crawler also includes:
- `status_label`
- `reason`
- `timestamps.state`
- `timestamps.message`
- `last_success_at`
- `last_attempt_at`
- `age_minutes`
- `threshold_minutes`

### Timestamp interpretation

Do not treat `null` timestamps as an outage by default.

Instead, read `crawlers.<name>.timestamps.state`:
- `recorded`: a successful timestamp exists
- `pending_first_success`: startup grace is active after restart/deploy
- `attempt_running`: a crawl is currently in progress
- `recovering`: DB activity exists and freshness timestamps have not caught up yet
- `missing`: no successful timestamp is currently recorded

## Health And Monitoring Tools

### `get_health()`

Purpose:
- one-stop system report for operators and bots

Returns:
- `status`
- `status_label`
- `summary`
- `recommended_action`
- `risk_level`
- `checked_at`
- `version`
- `database`
- `crawlers`
- `crawler_summary`
- `open_alerts`
- `open_alert_count`
- `pipeline_activity`
- compatibility aliases: `crawler`, `alerts`, `alert_count`

Important fields:
- `database.status`: `connected` or `disconnected`
- `crawler_summary.healthy`
- `crawler_summary.starting`
- `crawler_summary.running`
- `crawler_summary.recovering`
- `crawler_summary.attention_needed`

Usage guidance:
- if `status="ok"`, the system is healthy
- if `status="starting"`, wait for the first full crawler pass
- if `status="recovering"`, do not call it an outage; monitor logs and timestamps
- if `status="attention_needed"`, escalate and inspect scheduler behavior
- if `status="unhealthy"`, treat it as a real service/database issue

### `get_feed_freshness()`

Purpose:
- backward-compatible alias for `get_health()`

Behavior:
- returns the same core report as `get_health()`
- includes `tool_alias="get_feed_freshness"`

Guidance:
- new agents should use `get_health()` instead

## Discovery And Summary Tools

### `get_tracks()`

Purpose:
- list all available tracks

Returns:
- `tracks`
- `count`

Typical use:
- populate a track picker
- translate between track name and track code

### `get_recent_uploads(limit=10)`

Purpose:
- inspect recent DRF upload activity

Returns:
- `uploads`
- `count`
- `limit`

Typical use:
- confirm ingestion from uploads is happening
- inspect the most recent uploaded dates/tracks

### `get_filter_options(summary_date="")`

Purpose:
- get available dates and track filters
- get per-track summary for a target date

Returns:
- `dates`
- `tracks`
- `today_summary`
- `summary_date`

Typical use:
- populate dashboard filters
- show track cards for a given date

## Race And Card Tools

### `get_entries(track="", race_date="", race_number=0, include_scratched=True, limit=20)`

Purpose:
- fetch entries for a track/date/race slice

Parameters:
- `track`: track code like `GP`, `SA`, `AQU`
- `race_date`: `YYYY-MM-DD`
- `race_number`: optional race filter
- `include_scratched`: include scratched entries if `True`
- `limit`: max number of races returned

Typical use:
- “show me Gulfstream race 4 entries for April 6”

### `get_results(track="", race_date="", race_number=0, limit=20)`

Purpose:
- fetch result summaries for a track/date/race slice

Parameters:
- `track`
- `race_date`
- `race_number`
- `limit`

Typical use:
- “who won Santa Anita race 8 on April 2”

### `get_todays_races(track="", status="All")`

Purpose:
- fetch today’s race list with status filtering

Parameters:
- `track`
- `status`: `All`, `Upcoming`, `Completed`

Typical use:
- live race board
- “show me today’s completed races at Gulfstream”

### `get_past_races(track="", start_date="", end_date="", limit=50)`

Purpose:
- browse historical races

Parameters:
- `track`
- `start_date`
- `end_date`
- `limit`

Typical use:
- history browsing
- horse research

### `get_race_details(race_key)`

Purpose:
- get the full card view for a single race

Input:
- `race_key` like `GP-20260406-4`

Typical use:
- single-race detail page
- full result/scratch/entry context

### `get_race_changes(race_id)`

Purpose:
- get all change records for a single race

Input:
- `race_id`

Typical use:
- race-level late changes inspection
- debugging race-specific scratch/change behavior

Notes:
- this is broader than `get_scratches`
- it may include race-level and horse-level changes

## Horse Tools

### `get_horses(search="", limit=50, page=1, with_races=False)`

Purpose:
- search horses

Parameters:
- `search`
- `limit`
- `page`
- `with_races`

Typical use:
- horse search UI
- quick horse lookup

### `get_horse_profile(horse_id="", horse_name="")`

Purpose:
- get full horse profile

Input:
- either `horse_id` or `horse_name`

Typical use:
- profile page
- full history/stat lookup

Behavior notes:
- if `horse_name` matches multiple horses, the tool returns an ambiguity response instead of guessing

## Late Changes, Scratches, And Claims

### `get_scratches(view="upcoming", page=1, limit=20, track="All", start_date="", end_date="", race_number=0)`

Purpose:
- canonical scratches feed

Important:
- `get_scratches` is the scratches-first view
- it merges normalized scratch-type late changes with scratched race entries
- use this when you specifically want scratches

Parameters:
- `view`: `upcoming`, `history`, or `all`
- `page`
- `limit`
- `track`
- `start_date`
- `end_date`
- `race_number`

View semantics:
- `upcoming`: today/future-oriented feed
- `history`: strictly before today
- `all`: unrestricted date scope

Fallback behavior:
- if `upcoming` is empty and no explicit date range is provided, the tool may fall back to recent historical scratches
- when this happens, `meta.fallback_applied=true`

### `get_changes(view="upcoming", mode="", page=1, limit=20, track="All", start_date="", end_date="", race_number=0)`

Purpose:
- normalized late-changes feed

Important:
- this is broader than `get_scratches`
- it includes scratches plus other late changes such as:
  - jockey changes
  - weight changes
  - equipment changes
  - race cancellations
  - post-time changes
  - horse notes/program notes

Use:
- use `get_changes` for the full late-change picture
- use `get_scratches` when the user only wants scratches

Filtering:
- supports `track`, `start_date`, `end_date`, and `race_number`

### `get_claims(track="", start_date="", end_date="", race_number=0, limit=100)`

Purpose:
- fetch claims with race context

Important output fields:
- per claim:
  - `claimant_details_complete`
- in `meta`:
  - `missing_claimant_details`
  - `claims_with_complete_details`
  - `claimant_detail_coverage_pct`

How to interpret missing claimant details:
- empty `new_trainer_name` / `new_owner_name` usually means incomplete source extraction for that claim
- it should not be treated as an endpoint failure unless the whole feed is empty or broken

## Examples

### Example: one-stop health check

Use:
- `get_health()`

Interpretation:
- if `status="ok"`: no action needed
- if `status="starting"`: wait for startup grace to clear
- if `status="recovering"`: monitor, do not call it an outage yet
- if `status="attention_needed"`: investigate scheduler/crawler behavior

### Example: scratches for Gulfstream race 4 on April 6

Use:

```text
get_scratches(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)
```

### Example: all late changes for a specific race

Use:

```text
get_changes(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)
```

### Example: single-race results lookup

Use:

```text
get_results(track="SA", race_date="2026-04-02", race_number=8)
```

## Common Agent Mistakes To Avoid

Do not:
- infer outages from `last_success_at=null` without checking `status`
- call `recovering` a crawler outage
- call `starting` a failure state
- assume `get_changes` and `get_scratches` should return identical records
- assume missing claimant details in `get_claims` means the endpoint is broken
- assume the frontend hides data because the backend lacks it

Do:
- trust `get_health()` first
- read `summary` and `recommended_action`
- use targeted tools with `track`, `date`, and `race_number` when possible
- inspect `meta` on paginated feeds for view/fallback behavior

## Recommended Agent Workflow

When an agent needs to answer “is the system okay?”:
1. Call `get_health()`.
2. Read `status`.
3. Read `summary`.
4. Check `database.status`.
5. Check `crawler_summary`.
6. Only then inspect per-crawler timestamps if needed.

When an agent needs race-specific data:
1. Prefer `get_entries`, `get_results`, `get_scratches`, `get_changes`, or `get_claims`.
2. Pass explicit `track`, `date`, and `race_number` whenever possible.
3. Avoid broad historical scans unless the user actually asked for them.
