# Daily Scheduler Quick Start

## Quick Deploy on Raspberry Pi 5 (Docker/Portainer)

### Prerequisites

1. Docker and Portainer installed on Pi 5 (via Umbrel or standalone)
2. `.env` file with credentials:
   ```bash
   SUPABASE_URL=https://vytyhtddhplcrvvgidyy.supabase.co
   SUPABASE_SERVICE_KEY=your-service-key
   FIRECRAWL_API_KEY=fc-e0ac820386e840a791942dcc8cb5a6df
   ```

### Method 1: Docker Compose (Easiest)

```bash
# On your Pi 5
cd /home/pi/horse-racing-tool/backend

# Create logs directory
mkdir -p logs

# Build and start
docker-compose -f docker-compose.scheduler.yml up -d

# View logs
docker-compose -f docker-compose.scheduler.yml logs -f

# Stop
docker-compose -f docker-compose.scheduler.yml down
```

### Method 2: Portainer UI

1. **Build Image**
   ```bash
   cd /home/pi/horse-racing-tool
   docker build -f backend/Dockerfile.scheduler -t horse-racing-scheduler .
   ```

2. **Deploy via Portainer**
   - Open Portainer UI
   - Go to **Containers** → **Add Container**
   - **Name:** `horse-racing-scheduler`
   - **Image:** `horse-racing-scheduler:latest`
   - **Environment Variables:**
     - `SUPABASE_URL`: `https://vytyhtddhplcrvvgidyy.supabase.co`
     - `SUPABASE_SERVICE_KEY`: `your-key`
     - `FIRECRAWL_API_KEY`: `your-key`
     - `TZ`: `America/New_York`
   - **Volumes:**
     - Container: `/var/log`
     - Host: `/home/pi/horse-racing-tool/backend/logs`
   - **Restart Policy:** Always
   - Click **Deploy**

3. **View Logs**
   - Select container in Portainer
   - Click **Logs** tab

### Method 3: Traditional Cron (No Docker)

```bash
# Edit crontab
crontab -e

# Add:
0 1 * * * cd /home/pi/horse-racing-tool && /home/pi/horse-racing-tool/venv/bin/python3 /home/pi/horse-racing-tool/backend/daily_crawl.py >> /home/pi/horse-racing-tool/backend/logs/crawler.log 2>&1

# Save and exit
```

## Testing

### Manual Test Run

```bash
# Docker method
docker exec horse-racing-scheduler python3 /app/backend/daily_crawl.py

# Cron method
cd /home/pi/horse-racing-tool
source venv/bin/activate
python3 backend/daily_crawl.py
```

### Check Database Logs

```sql
SELECT
  crawl_date,
  status,
  tracks_processed,
  races_updated,
  duration_seconds,
  started_at
FROM hranalyzer_crawl_logs
ORDER BY started_at DESC
LIMIT 5;
```

## Schedule Details

- **Time:** 1:00 AM daily (configurable in `backend/crontab`)
- **Action:** Crawls previous day's races
- **Tracks:** 15 common US tracks (configurable in `crawl_equibase.py`)
- **Output:** Logs to `/var/log/horse-racing-crawler.log`

## Monitoring

### Docker Logs
```bash
docker logs -f horse-racing-scheduler
```

### Cron Logs
```bash
tail -f /home/pi/horse-racing-tool/backend/logs/crawler.log
```

### Healthcheck (Optional)

Add to `daily_crawl.py` after successful crawl:
```python
import requests
requests.get("https://hc-ping.com/your-uuid")
```

Sign up at https://healthchecks.io for free monitoring.

## Troubleshooting

**Container keeps restarting:**
```bash
docker logs horse-racing-scheduler
# Check for configuration errors
```

**No races being crawled:**
- Check Firecrawl API key is valid
- Verify network connectivity from Pi
- Check logs for specific errors

**Cron not running:**
```bash
sudo systemctl status cron
crontab -l  # Verify job is listed
```

## Cost Estimate

- ~15 tracks × 10 races = 150 API calls/day
- ~4,500 API calls/month
- Check your Firecrawl plan limits

## Next Steps

1. Deploy using one of the methods above
2. Wait 24 hours for first automatic run
3. Check logs and database
4. Monitor for a week
5. Adjust tracks/schedule as needed

For detailed documentation, see `DAILY_CRAWLER_SETUP.md`.
