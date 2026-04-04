# Operator Runbook

Use this when operating the live Pi/Portainer deployment.

## Deploy

Update the repo on the Pi:

```bash
cd ~/horserace-analyzer
git checkout main
git pull --ff-only origin main
git rev-parse --short HEAD
```

Then redeploy in Portainer with `Update the stack`.

## Health Checks

Backend:

```bash
curl -4 http://127.0.0.1:5001/api/health
curl -4 http://127.0.0.1:5001/api/health/live
```

MCP:

```bash
curl -4 --max-time 5 -i -H 'Accept: text/event-stream' http://127.0.0.1:8001/mcp
```

## One-Stop Health Output

Treat `/api/health` and MCP `get_health()` as the source of truth.

Trust these fields first:
- `status`
- `status_label`
- `summary`
- `recommended_action`
- `database.status`
- `crawler_summary`

Top-level states:
- `ok`: system health looks good
- `starting`: startup grace is active after restart/deploy
- `monitor_delay`: live data exists, but freshness timestamps are lagging
- `attention_needed`: one or more crawlers truly need investigation
- `degraded`: crawler freshness is okay, but another runtime alert is open
- `unhealthy`: database or core service health failed

Do not infer outages from `last_success_at` alone.

If a timestamp is `null`, read:
- `crawlers.<name>.timestamps.state`
- `crawlers.<name>.timestamps.message`

## Alerting

Discord alerts are intended for real issues only:
- startup grace suppresses deploy noise
- crawl alerts require multiple consecutive stale evaluations before opening
- resolved alerts indicate the issue cleared on a later successful pass

Old Discord messages remain in channel history even after the live alert is resolved. Check `/api/health` for current truth.

## Common Triage

If races are missing from the dashboard:
- check `/api/health`
- check scheduler logs in Portainer
- verify `/api/filter-options` still returns data

If final race results are stuck:
- unresolved same-day races are retried before the broad results sweep
- check scheduler logs for repeated PDF `404` misses

If scratches/changes are missing for a track:
- check `/api/scratches` or MCP `get_scratches` with explicit `track`, `start_date`, `end_date`, and `race_number`
- check scheduler logs for RSS / late-changes fetch failures

## Key Docs

- [MCP tools](./MCP_TOOLS.md)
- [Crawler setup](./DAILY_CRAWLER_SETUP.md)
- [Scheduler quickstart](./SCHEDULER_QUICKSTART.md)
