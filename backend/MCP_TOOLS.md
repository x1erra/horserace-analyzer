# MCP Tools

The TrackData MCP server is read-only and runs at `http://<host>:8001/mcp`.

## Freshness

Use `get_feed_freshness()` as the source of truth for crawler health.

How to read it:
- `status` is the top-level answer. Trust this first.
- `status="healthy"` means crawler freshness is good.
- `status="healthy"` can also mean the live pipeline is healthy even if `monitoring_status="desynced"` indicates freshness timestamps are lagging behind recent DB activity.
- `status="warming_up"` means the stack recently restarted and startup grace is active.
- `status="stale"` means one or more crawlers are genuinely stale and recent pipeline activity does not contradict that.
- `status="degraded"` means crawler freshness is current, but there are other open runtime alerts.
- `monitoring_status` tells you whether the freshness monitor itself is current, warming up, stale, or desynced.
- `stale_crawlers`, `warming_up_crawlers`, and `in_progress_crawlers` are the next fields to inspect.
- `crawler.<name>.status` is one of `fresh`, `in_progress`, `warming_up`, or `stale`.
- `crawler.<name>.reason` explains that crawler’s state in plain English.
- `risk_level` and `recommended_action` are intended for bots/operators to summarize the situation without guessing.
- Do not infer freshness from `last_success_at` alone without checking `status`.

## Targeted race/card tools

Use these for precise questions instead of broad feeds:
- `get_entries(track, race_date, race_number, include_scratched, limit)`
- `get_results(track, race_date, race_number, limit)`
- `get_scratches(view, track, start_date, end_date, race_number, page, limit)`
- `get_changes(view|mode, track, start_date, end_date, race_number, page, limit)`
- `get_claims(track, start_date, end_date, race_number, limit)`

Examples:
- “What scratches occurred at Gulfstream on April 6 for race 4?”
  - `get_scratches(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)`
- “Show me Santa Anita race 8 results for April 2.”
  - `get_results(track="SA", race_date="2026-04-02", race_number=8)`

Scratch/change semantics:
- `get_scratches` is the canonical scratches feed. It merges normalized scratch-type late changes with scratched race entries, so it can surface scratches even when the late-change record lands before every database side effect has propagated.
- `get_changes` is broader. It includes scratches plus jockey, weight, equipment, cancellation, and post-time changes.
- If you only care about scratches, prefer `get_scratches`.
- If you want the full late-changes picture for a race/card, use `get_changes`.

Claims semantics:
- `get_claims` returns `meta.missing_claimant_details` and per-claim `claimant_details_complete`.
- Empty `new_trainer` / `new_owner` fields should be treated as incomplete source extraction for that claim, not as a failed endpoint.

## Feed views

For `get_scratches` and `get_changes`:
- `view="upcoming"` means today/future-focused data.
- `view="all"` means include historical data.
- If `upcoming` is empty, the MCP tool may fall back to recent historical data and will say so in `meta`.
