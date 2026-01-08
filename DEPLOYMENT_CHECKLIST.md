# Deployment Checklist for Raspberry Pi 5

Complete checklist for deploying the Horse Racing Tool to Raspberry Pi 5.

## Pre-Deployment Checklist

### ☐ Environment Setup

- [ ] Raspberry Pi 5 is set up and accessible via SSH
- [ ] Docker is installed on Pi 5 (`docker --version`)
- [ ] Docker Compose is installed (`docker-compose --version`)
- [ ] Portainer is running (if using Portainer deployment)
- [ ] Pi 5 has at least 2GB free disk space
- [ ] Pi 5 has stable internet connection

### ☐ Credentials Ready

- [ ] Supabase URL copied from dashboard
- [ ] Supabase Service Role Key copied (NOT anon key)
- [ ] Firecrawl API key ready
- [ ] Firecrawl account has sufficient credits

### ☐ Database Prepared

- [ ] Supabase project created
- [ ] Database schema deployed (`db_schema.sql`)
- [ ] All `hranalyzer_*` tables exist
- [ ] Test connection with service key works

### ☐ Code Ready

- [ ] Latest code committed to git
- [ ] All changes tested locally
- [ ] `.env.example` is up to date
- [ ] Docker files are present

## Deployment Steps

### Step 1: Transfer Code to Pi 5

```bash
# Choose one method:

# Method A: Git clone (recommended)
ssh pi@raspberrypi.local
cd /home/pi
git clone https://github.com/yourusername/horse-racing-tool.git
cd horse-racing-tool

# Method B: Rsync from dev machine
rsync -avz --exclude 'node_modules' --exclude 'venv' --exclude '.git' \
  ~/Projects/horse-racing-tool/ pi@raspberrypi.local:~/horse-racing-tool/
```

**Verification:**
- [ ] Code is on Pi at `/home/pi/horse-racing-tool`
- [ ] All files present: `ls -la`
- [ ] Docker files exist: `ls -la Dockerfile*`

### Step 2: Configure Environment

```bash
cd /home/pi/horse-racing-tool

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

Add your credentials:
```env
SUPABASE_URL=https://vytyhtddhplcrvvgidyy.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJI...your-actual-key
FIRECRAWL_API_KEY=fc-e0ac82...your-actual-key
```

**Verification:**
- [ ] `.env` file exists
- [ ] All three credentials are set
- [ ] No quotes around values
- [ ] No extra spaces

### Step 3: Create Required Directories

```bash
mkdir -p logs uploads
chmod 755 logs uploads
```

**Verification:**
- [ ] `logs/` directory exists
- [ ] `uploads/` directory exists
- [ ] Permissions are correct: `ls -ld logs uploads`

### Step 4: Build Docker Images

```bash
# Build backend
docker build -t horse-racing-backend:latest .

# Build scheduler
docker build -f Dockerfile.scheduler -t horse-racing-scheduler:latest .
```

**Verification:**
- [ ] Backend image built successfully
- [ ] Scheduler image built successfully
- [ ] Check images: `docker images | grep horse-racing`

### Step 5: Deploy Containers

Choose deployment method:

#### Option A: Full Stack (Recommended)

```bash
docker-compose up -d
```

**Verification:**
- [ ] Both containers started: `docker ps`
- [ ] Backend is healthy: `docker ps --format "table {{.Names}}\t{{.Status}}"`
- [ ] Scheduler is running: `docker ps | grep scheduler`

#### Option B: Production Stack (with resource limits)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### Option C: Scheduler Only

```bash
docker-compose -f docker-compose.scheduler.yml up -d
```

### Step 6: Verify Deployment

```bash
# Check container status
docker ps

# View logs
docker-compose logs -f

# Test backend health
curl http://localhost:5001/api/health

# Test API endpoints
curl http://localhost:5001/api/todays-races
curl http://localhost:5001/api/past-races?limit=5
```

**Verification:**
- [ ] Backend container is "healthy" status
- [ ] Health endpoint returns 200 OK
- [ ] API endpoints return JSON
- [ ] Scheduler container is running
- [ ] Cron is running: `docker-compose exec scheduler pgrep cron`

### Step 7: Test Crawler

```bash
# Manual crawler test
docker-compose exec scheduler python3 /app/backend/daily_crawl.py

# View crawler logs
docker-compose exec scheduler tail -50 /var/log/horse-racing-crawler.log
```

**Verification:**
- [ ] Crawler script runs without errors
- [ ] Database connection succeeds
- [ ] Logs are being written
- [ ] Either results are fetched OR Firecrawl credit error (expected if no credits)

### Step 8: Monitor for 24 Hours

```bash
# Check logs periodically
docker-compose logs --tail=100 -f

# Check resource usage
docker stats

# Verify cron ran (after 1 AM)
docker-compose exec scheduler tail -100 /var/log/horse-racing-crawler.log | grep "Starting crawl"
```

**Verification:**
- [ ] Containers stay running for 24 hours
- [ ] Memory usage stays under 512MB (backend) and 256MB (scheduler)
- [ ] CPU usage is reasonable
- [ ] Cron job executed at 1 AM
- [ ] No critical errors in logs

## Post-Deployment Configuration

### Optional: Set Up Reverse Proxy

If you want external access:

```bash
# Install Nginx
sudo apt install nginx

# Configure reverse proxy
sudo nano /etc/nginx/sites-available/horse-racing
```

### Optional: Enable HTTPS

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com
```

### Optional: Set Up Monitoring

1. **Healthchecks.io** (free tier available)
   - Sign up at https://healthchecks.io
   - Create new check for daily crawler
   - Add ping URL to `daily_crawl.py`

2. **Uptime Kuma** (self-hosted)
   - Deploy via Docker
   - Monitor backend health endpoint
   - Set up alerts

### Optional: Automated Backups

```bash
# Create backup script
nano /home/pi/backup-horse-racing.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
cd /home/pi/horse-racing-tool
tar -czf /home/pi/backups/horse-racing-$DATE.tar.gz \
  .env docker-compose*.yml logs/
```

Add to crontab:
```bash
crontab -e
# Add: 0 3 * * * /home/pi/backup-horse-racing.sh
```

## Troubleshooting Checklist

### Container Won't Start

- [ ] Check logs: `docker-compose logs backend`
- [ ] Verify `.env` file has all credentials
- [ ] Check port 5001 is not in use: `sudo lsof -i :5001`
- [ ] Verify database connection manually
- [ ] Check Docker daemon: `sudo systemctl status docker`

### Crawler Not Running

- [ ] Cron is running: `docker-compose exec scheduler pgrep cron`
- [ ] Crontab is loaded: `docker-compose exec scheduler crontab -l`
- [ ] Manually run: `docker-compose exec scheduler python3 /app/backend/daily_crawl.py`
- [ ] Check Firecrawl credits
- [ ] View logs: `docker-compose exec scheduler tail -100 /var/log/horse-racing-crawler.log`

### High Memory Usage

- [ ] Check stats: `docker stats`
- [ ] Use production compose: `docker-compose -f docker-compose.prod.yml`
- [ ] Increase swap space on Pi
- [ ] Reduce crawler frequency
- [ ] Deploy backend and scheduler on separate Pis

### API Not Responding

- [ ] Check container health: `docker ps`
- [ ] View backend logs: `docker-compose logs backend`
- [ ] Test database connection
- [ ] Restart backend: `docker-compose restart backend`
- [ ] Check network: `docker network inspect horse-racing-tool_horse-racing-network`

## Rollback Plan

If deployment fails:

```bash
# Stop containers
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Remove images
docker rmi horse-racing-backend:latest
docker rmi horse-racing-scheduler:latest

# Restore from backup (if available)
cd /home/pi
tar -xzf backups/horse-racing-YYYYMMDD.tar.gz -C horse-racing-tool/
```

## Success Criteria

Deployment is successful when:

- [ ] ✅ Both containers running and healthy for 24+ hours
- [ ] ✅ Backend API responds to all endpoints
- [ ] ✅ Database connection working
- [ ] ✅ Crawler executes daily at 1 AM
- [ ] ✅ Logs are being written correctly
- [ ] ✅ Memory usage stays under limits
- [ ] ✅ No critical errors in 24-hour logs
- [ ] ✅ Can upload DRF PDF and see results
- [ ] ✅ Can view past races and race details

## Maintenance Schedule

### Daily
- [ ] Check container status: `docker ps`
- [ ] Review yesterday's crawler log
- [ ] Monitor memory usage: `docker stats`

### Weekly
- [ ] Review all logs for errors
- [ ] Check disk space: `df -h`
- [ ] Verify Firecrawl API credits
- [ ] Test manual crawler run

### Monthly
- [ ] Update Docker images: `docker-compose pull`
- [ ] Review and clean old logs: `find logs/ -name "*.log" -mtime +30 -delete`
- [ ] Check database size in Supabase
- [ ] Test backup restoration

## Support Resources

- **Documentation:** `/home/pi/horse-racing-tool/DOCKER_DEPLOYMENT.md`
- **Integration Tests:** `/home/pi/horse-racing-tool/backend/INTEGRATION_TEST_RESULTS.md`
- **Scheduler Guide:** `/home/pi/horse-racing-tool/backend/SCHEDULER_QUICKSTART.md`
- **GitHub Issues:** [Create issue](https://github.com/yourusername/horse-racing-tool/issues)

---

**Last Updated:** 2026-01-07
**Deployment Target:** Raspberry Pi 5 with Docker/Portainer
