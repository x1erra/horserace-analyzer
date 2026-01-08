# Complete Deployment Guide - Raspberry Pi 5

**Follow these exact steps to deploy your horse racing data pipeline.**

---

## Prerequisites Checklist

Before you start, make sure you have:

- [ ] Raspberry Pi 5 powered on and connected to network
- [ ] SSH access to your Pi (test: `ssh pi@raspberrypi.local`)
- [ ] Docker installed on Pi (test: `ssh pi@raspberrypi.local "docker --version"`)
- [ ] Docker Compose installed (test: `ssh pi@raspberrypi.local "docker-compose --version"`)
- [ ] Supabase project created at https://supabase.com
- [ ] Your Supabase credentials ready:
  - Project URL (looks like: `https://abcdefgh.supabase.co`)
  - Service Role Key (NOT anon key - get from Settings → API)

---

## Step 1: Transfer Code to Raspberry Pi

### Option A: Using Git (Recommended if you have GitHub)

```bash
# On your Mac (development machine)
cd ~/Projects/horse-racing-tool

# First, commit all changes
git add .
git commit -m "Complete system with free local parsing"
git push

# SSH to Pi
ssh pi@raspberrypi.local

# Clone on Pi
cd /home/pi
git clone https://github.com/YOUR_USERNAME/horse-racing-tool.git
cd horse-racing-tool
```

### Option B: Using rsync (If no GitHub)

```bash
# On your Mac (development machine)
cd ~/Projects

# Transfer files to Pi
rsync -avz --exclude 'node_modules' --exclude 'venv' --exclude '.git' --exclude 'logs' --exclude 'uploads' \
  horse-racing-tool/ pi@raspberrypi.local:~/horse-racing-tool/

# Verify transfer
ssh pi@raspberrypi.local "ls -la ~/horse-racing-tool"
```

**✓ Verify:** You should see all project files on Pi

---

## Step 2: Configure Supabase Database

### 2.1: Get Your Supabase Credentials

1. Go to https://supabase.com/dashboard
2. Open your project
3. Click **Settings** (gear icon) → **API**
4. Copy these two values:
   - **Project URL** (under "Config")
   - **service_role key** (under "Project API keys" - NOT the anon key!)

### 2.2: Deploy Database Schema

1. In Supabase dashboard, click **SQL Editor**
2. Click **New Query**
3. On your Mac, copy the schema:
   ```bash
   cat backend/db_schema.sql
   ```
4. Paste into Supabase SQL Editor
5. Click **Run** (or press Cmd+Enter)
6. **✓ Verify:** You should see "Success. No rows returned" and 10 new tables in your Database tab

---

## Step 3: Configure Environment on Pi

```bash
# SSH to Pi (if not already)
ssh pi@raspberrypi.local

# Navigate to project
cd ~/horse-racing-tool

# Create .env file from template
cp .env.example .env

# Edit the file
nano .env
```

**In nano editor, enter:**
```env
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...YOUR_ACTUAL_KEY
```

**Important:**
- Replace `YOUR_PROJECT_ID` with your actual Supabase project ID
- Replace the entire `eyJ...` string with your actual service_role key
- No quotes around the values
- No spaces around the `=` signs

**Save and exit:**
- Press `Ctrl+X`
- Press `Y` to confirm
- Press `Enter` to save

**✓ Verify your .env:**
```bash
cat .env
```
Should show your two credentials.

---

## Step 4: Create Required Directories

```bash
# Still on Pi
cd ~/horse-racing-tool

# Create directories
mkdir -p logs uploads

# Set permissions
chmod 755 logs uploads

# ✓ Verify
ls -ld logs uploads
```

You should see both directories with `drwxr-xr-x` permissions.

---

## Step 5: Build Docker Images

```bash
# Still on Pi
cd ~/horse-racing-tool

# Build both images (this takes 5-10 minutes on Pi)
docker build -t horse-racing-backend:latest .
docker build -f Dockerfile.scheduler -t horse-racing-scheduler:latest .

# ✓ Verify images were built
docker images | grep horse-racing
```

You should see both images listed.

**Note:** If build fails with memory errors, try:
```bash
# Increase swap space temporarily
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## Step 6: Deploy Containers

```bash
# Still on Pi
cd ~/horse-racing-tool

# Start all services
docker-compose up -d

# Wait 10 seconds for containers to start
sleep 10

# ✓ Verify containers are running
docker-compose ps
```

**You should see:**
```
NAME                        STATUS          PORTS
horse-racing-backend        Up (healthy)    0.0.0.0:5001->5001/tcp
horse-racing-scheduler      Up
```

If status shows "unhealthy" or "restarting", check logs:
```bash
docker-compose logs backend
docker-compose logs scheduler
```

---

## Step 7: Test the System

### 7.1: Test Backend API

```bash
# Test health endpoint (from Pi)
curl http://localhost:5001/api/health

# Should return:
# {"status":"ok"}

# Test races endpoint
curl http://localhost:5001/api/todays-races

# Should return:
# {"count":0,"date":"2026-01-07","races":[]}

# Test past races endpoint
curl http://localhost:5001/api/past-races?limit=5

# Should return JSON with your existing GP races
```

### 7.2: Test from Your Mac

```bash
# From your Mac (replace raspberrypi.local with Pi's IP if needed)
curl http://raspberrypi.local:5001/api/health

# Should return:
# {"status":"ok"}
```

### 7.3: Test Crawler Manually

```bash
# On Pi
docker-compose exec scheduler python3 /app/backend/daily_crawl.py --date 2026-01-01

# This will attempt to crawl races from Jan 1, 2026
# Watch for successful parsing (or expected 404s for future dates)
```

**✓ Expected output:**
```
INFO: Starting Equibase crawler for 2026-01-01
INFO: Starting crawl for 2026-01-01
INFO: Tracks to check: AQU, BEL, CD, ...
INFO: Processing track: GP
INFO: Downloading PDF from https://www.equibase.com/...
```

---

## Step 8: Verify Database Connection

```bash
# Check crawl logs table
# Go to Supabase dashboard → Table Editor → hranalyzer_crawl_logs

# You should see at least one entry from your manual test
```

---

## Step 9: Set Up Frontend (Optional - for local access)

If you want to access the web interface from your Mac:

### Option 1: Access directly from Mac

```bash
# On your Mac, open browser to:
http://raspberrypi.local:5001/api/health

# For React frontend, you'll need to build and serve it
```

### Option 2: Build frontend on Pi (Advanced)

```bash
# On Pi
cd ~/horse-racing-tool

# Install Node.js if not installed
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Build frontend
npm install
npm run build

# Serve with simple HTTP server
npx serve -s dist -p 3000

# Access from Mac:
# http://raspberrypi.local:3000
```

---

## Step 10: Monitor for 24 Hours

### Check Logs

```bash
# View all logs
docker-compose logs -f

# View just backend
docker-compose logs -f backend

# View just scheduler
docker-compose logs -f scheduler

# View crawler log file
docker-compose exec scheduler tail -f /var/log/horse-racing-crawler.log
```

### Check Container Status

```bash
# See running containers
docker-compose ps

# See resource usage
docker stats

# See health status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Verify Cron Schedule

```bash
# Check cron is running
docker-compose exec scheduler pgrep cron

# View crontab
docker-compose exec scheduler crontab -l

# Should show:
# 0 1 * * * cd /app && /usr/local/bin/python3 /app/backend/daily_crawl.py...
```

---

## Step 11: Test First Automatic Crawl

The crawler runs at **1:00 AM daily**.

**Next morning, check:**

```bash
# On Pi, check if crawler ran
docker-compose exec scheduler tail -100 /var/log/horse-racing-crawler.log

# Look for:
# "Starting Equibase crawler for YYYY-MM-DD"
# "Crawl Summary:"

# Check database
# Go to Supabase → Table Editor → hranalyzer_crawl_logs
# Should see new entry with timestamp around 1 AM
```

---

## Step 12: Upload Your First DRF PDF

### From Your Mac (if backend is accessible):

1. Get a DRF PDF for today's races
2. Open browser to: `http://raspberrypi.local:5001` (if you set up frontend)
3. Or use curl:

```bash
# From Mac
curl -X POST -F "file=@/path/to/your/drf.pdf" \
  http://raspberrypi.local:5001/api/upload-drf
```

### Or copy PDF to Pi and upload:

```bash
# Copy PDF to Pi
scp ~/path/to/drf.pdf pi@raspberrypi.local:~/

# On Pi
cd ~
curl -X POST -F "file=@drf.pdf" http://localhost:5001/api/upload-drf
```

**✓ Verify:** Check Supabase database - should see new races in `hranalyzer_races` table

---

## Complete Verification Checklist

After deployment, verify everything is working:

- [ ] Backend container is running and healthy
- [ ] Scheduler container is running
- [ ] Health endpoint returns `{"status":"ok"}`
- [ ] API endpoints return valid JSON
- [ ] Crawler can run manually without errors
- [ ] Database connection working (check Supabase logs table)
- [ ] Cron job scheduled (runs at 1 AM)
- [ ] Can upload DRF PDF successfully
- [ ] Logs are being written to `/var/log`
- [ ] Containers survive reboot: `sudo reboot` then check `docker-compose ps`

---

## Useful Commands Reference

### Container Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# View logs
docker-compose logs -f

# Shell into backend
docker-compose exec backend /bin/bash

# Shell into scheduler
docker-compose exec scheduler /bin/bash
```

### Testing

```bash
# Test API
curl http://localhost:5001/api/health
curl http://localhost:5001/api/todays-races
curl http://localhost:5001/api/past-races?limit=5

# Manual crawler run
docker-compose exec scheduler python3 /app/backend/daily_crawl.py

# Check crawler log
docker-compose exec scheduler tail -100 /var/log/horse-racing-crawler.log

# Check cron status
docker-compose exec scheduler pgrep cron
docker-compose exec scheduler crontab -l
```

### Monitoring

```bash
# Resource usage
docker stats

# Container status
docker-compose ps

# Disk space
df -h

# View logs
docker-compose logs --tail=100 -f
```

---

## Troubleshooting Common Issues

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Common fixes:
# 1. Check .env file has correct credentials
# 2. Verify port 5001 isn't in use: sudo lsof -i :5001
# 3. Check disk space: df -h
```

### Database connection error

```bash
# Verify credentials in .env
cat .env

# Test Supabase connection manually
docker-compose exec backend python3 -c "
from backend.supabase_client import get_supabase_client
supabase = get_supabase_client()
result = supabase.table('hranalyzer_tracks').select('id').limit(1).execute()
print('Connection OK:', result.data)
"
```

### Crawler not running

```bash
# Check cron is running
docker-compose exec scheduler pgrep cron

# If not running, restart scheduler
docker-compose restart scheduler

# Test crawler manually
docker-compose exec scheduler python3 /app/backend/daily_crawl.py
```

### Out of memory

```bash
# Check memory usage
free -h
docker stats

# Increase swap if needed
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Use production compose with resource limits
docker-compose -f docker-compose.prod.yml up -d
```

---

## Next Steps After Deployment

### Week 1:
1. Monitor logs daily
2. Verify crawler runs at 1 AM each night
3. Upload at least one DRF PDF
4. Check database growth in Supabase

### Month 1:
5. Review crawler success rate
6. Add more tracks if needed (edit `backend/crawl_equibase.py`)
7. Set up monitoring (healthchecks.io)
8. Configure automated backups

### Month 2+:
9. Analyze historical data
10. Build custom queries
11. Start exploring predictive modeling
12. Consider adding live odds integration

---

## Support

If you run into issues:

1. **Check logs first:**
   ```bash
   docker-compose logs -f
   ```

2. **Check documentation:**
   - `DOCKER_DEPLOYMENT.md` - Comprehensive guide
   - `DEPLOYMENT_CHECKLIST.md` - Detailed checklist
   - `FREE_OPERATION_UPDATE.md` - Technical details
   - `INTEGRATION_TEST_RESULTS.md` - Expected behavior

3. **Verify environment:**
   ```bash
   cat .env
   docker-compose ps
   docker stats
   ```

4. **Test components individually:**
   ```bash
   # Test database
   curl http://localhost:5001/api/health

   # Test parser
   docker-compose exec backend python3 -c "import pdfplumber; print('OK')"

   # Test crawler
   docker-compose exec scheduler python3 /app/backend/crawl_equibase.py
   ```

---

## Success! 🎉

Once all containers are running and tests pass, your system is fully deployed!

**You now have:**
- ✅ Automated daily race data collection (100% FREE)
- ✅ DRF PDF upload and parsing
- ✅ Supabase database with historical data
- ✅ RESTful API for data access
- ✅ Docker containers running on Pi 5
- ✅ Scheduled cron jobs

**Cost to operate: $0/month**

**Next:** Wait for races to run, watch the crawler collect data automatically at 1 AM each night, and start building your analysis tools!

---

**Deployment completed:** `date`
**System status:** Production ready
**Operating cost:** $0/month
