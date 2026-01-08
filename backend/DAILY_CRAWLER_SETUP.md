# Daily Crawler Setup Guide

## Overview

The daily crawler automatically runs every day at 1:00 AM to crawl the previous day's race results from Equibase and insert them into your database.

## Features

- ✅ Automatic date calculation (crawls yesterday's races)
- ✅ Comprehensive logging with rotation
- ✅ Database connection validation before crawling
- ✅ Crawl statistics logged to `hranalyzer_crawl_logs` table
- ✅ Exit codes for monitoring (0=success, 1=no races, 2=failed, 3=db error, 4=config error)
- ✅ Log rotation when file exceeds 10MB

## Deployment Options

You have two options for deploying the daily crawler on your Raspberry Pi 5:

### Option A: Traditional Cron (Simpler)

#### 1. Set Up Environment

Make sure your `.env` file is in place:
```bash
cd /home/pi/horse-racing-tool/backend
cat .env  # Should show FIRECRAWL_API_KEY and SUPABASE_URL
```

#### 2. Test the Script Manually

```bash
cd /home/pi/horse-racing-tool
source venv/bin/activate
python3 backend/daily_crawl.py
```

Check the output and logs in `backend/horse-racing-crawler.log`

#### 3. Install Cron Job

```bash
# Edit crontab
crontab -e

# Add this line (runs at 1:00 AM every day):
0 1 * * * cd /home/pi/horse-racing-tool && /home/pi/horse-racing-tool/venv/bin/python3 /home/pi/horse-racing-tool/backend/daily_crawl.py >> /var/log/horse-racing-crawler.log 2>&1
```

**Note:** If you don't have write access to `/var/log`, the script will automatically use `backend/horse-racing-crawler.log` instead.

#### 4. Verify Cron Setup

```bash
# List your cron jobs
crontab -l

# Monitor the log file tomorrow morning
tail -f /var/log/horse-racing-crawler.log
# or
tail -f backend/horse-racing-crawler.log
```

#### 5. Log Rotation (Optional)

The script has built-in log rotation, but you can also use logrotate:

```bash
sudo nano /etc/logrotate.d/horse-racing-crawler

# Add:
/var/log/horse-racing-crawler.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

### Option B: Docker Container with Cron (Recommended for Umbrel/Portainer)

This option is better integrated with your Umbrel + Portainer setup.

#### 1. Create Dockerfile for Scheduler

See `Dockerfile.scheduler` in the backend directory.

#### 2. Build Docker Image

```bash
cd /home/pi/horse-racing-tool
docker build -f backend/Dockerfile.scheduler -t horse-racing-scheduler .
```

#### 3. Deploy via Portainer

1. Open Portainer UI on your Pi 5
2. Go to **Containers** → **Add Container**
3. Configure:
   - **Name:** `horse-racing-scheduler`
   - **Image:** `horse-racing-scheduler:latest`
   - **Environment Variables:**
     - `SUPABASE_URL`: `https://vytyhtddhplcrvvgidyy.supabase.co`
     - `SUPABASE_SERVICE_KEY`: `your-service-key`
     - `FIRECRAWL_API_KEY`: `your-firecrawl-key`
   - **Volumes:**
     - `/home/pi/horse-racing-tool/logs:/var/log` (for logs)
   - **Restart Policy:** Always
   - **Network:** bridge

4. Click **Deploy Container**

#### 4. Monitor Logs

In Portainer:
- Select the `horse-racing-scheduler` container
- Click **Logs** tab
- View real-time output

Or via command line:
```bash
docker logs -f horse-racing-scheduler
```

#### 5. Manual Trigger (for testing)

```bash
# Run crawler immediately
docker exec horse-racing-scheduler python3 /app/backend/daily_crawl.py
```

---

## Monitoring

### Check Crawl Status in Database

```sql
-- View recent crawl runs
SELECT
  crawl_date,
  status,
  tracks_processed,
  races_updated,
  duration_seconds,
  started_at
FROM hranalyzer_crawl_logs
ORDER BY started_at DESC
LIMIT 10;
```

### Check Logs

```bash
# For cron setup
tail -f /var/log/horse-racing-crawler.log

# For Docker setup
docker logs -f horse-racing-scheduler
```

### Exit Codes

The script uses these exit codes for monitoring:

- `0` - Success
- `1` - No races found (warning, not an error)
- `2` - Crawl failed
- `3` - Database error
- `4` - Configuration error (missing API keys)

## Troubleshooting

### "FIRECRAWL_API_KEY not set"

**Cron:**
```bash
# Check .env file
cat /home/pi/horse-racing-tool/backend/.env
```

**Docker:**
- Verify environment variables in Portainer container settings
- Restart container after updating

### "Database connection failed"

- Check network connectivity
- Verify SUPABASE_URL and SUPABASE_SERVICE_KEY
- Check if Supabase is accessible from your Pi

### Cron job not running

```bash
# Check cron service
sudo systemctl status cron

# Check system logs
sudo journalctl -u cron -f

# Verify crontab
crontab -l
```

### No races found every day

- Check if you're using the correct year (currently limited to 2026)
- Verify Equibase URLs are correct
- Check if races actually ran that day (holidays, weather cancellations)

## Testing the Crawler

### Manual Test Run

```bash
cd /home/pi/horse-racing-tool
source venv/bin/activate

# Run for yesterday
python3 backend/daily_crawl.py

# Check output
cat backend/horse-racing-crawler.log
```

### Test Specific Date

Modify `crawl_equibase.py` temporarily:
```python
# In daily_crawl.py, change:
yesterday = date.today() - timedelta(days=1)
# to:
yesterday = date(2026, 1, 4)  # Specific test date
```

## Cost Monitoring

The daily crawler will make approximately:
- 15 tracks × ~10 races per track = **~150 API calls per day**
- At Firecrawl's pricing, monitor your usage carefully
- Consider reducing the `COMMON_TRACKS` list if needed

## Next Steps

1. Choose your deployment option (A or B)
2. Test manually for 2-3 days
3. Verify crawl logs in database
4. Set up monitoring/alerts (optional)
5. Let it run automatically

## Advanced: Healthcheck Integration

For production monitoring, you can integrate with services like:

- **Healthchecks.io** - Free tier available
- **UptimeRobot** - Free tier available
- **Custom webhook** - Hit an endpoint after successful crawl

Example healthcheck integration:
```python
# Add to daily_crawl.py after successful crawl
import requests
HEALTHCHECK_URL = "https://hc-ping.com/your-uuid"
requests.get(HEALTHCHECK_URL)
```
