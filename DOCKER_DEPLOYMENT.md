# Docker Deployment Guide for Raspberry Pi 5

Complete guide for deploying the Horse Racing Tool on Raspberry Pi 5 using Docker and Portainer.

## Prerequisites

- Raspberry Pi 5 with Umbrel installed (or standalone Docker + Portainer)
- Docker and Docker Compose installed
- Portainer UI accessible
- Minimum 2GB RAM recommended
- Internet connection for API calls

## Quick Start (TL;DR)

```bash
# On your Raspberry Pi 5
cd /home/pi/horse-racing-tool

# Copy environment file and configure
cp .env.example .env
nano .env  # Add your API keys

# Deploy full stack
docker-compose up -d

# Or deploy only scheduler
docker-compose -f docker-compose.scheduler.yml up -d

# View logs
docker-compose logs -f
```

## Detailed Deployment Steps

### 1. Transfer Code to Raspberry Pi

```bash
# From your development machine
rsync -avz --exclude 'node_modules' --exclude 'venv' --exclude '.git' \
  /path/to/horse-racing-tool/ pi@raspberrypi.local:/home/pi/horse-racing-tool/
```

Or use git:
```bash
# On Raspberry Pi
cd /home/pi
git clone https://github.com/yourusername/horse-racing-tool.git
cd horse-racing-tool
```

### 2. Configure Environment Variables

```bash
cd /home/pi/horse-racing-tool
cp .env.example .env
nano .env
```

Fill in your credentials:
```env
SUPABASE_URL=https://vytyhtddhplcrvvgidyy.supabase.co
SUPABASE_SERVICE_KEY=your-actual-service-key
FIRECRAWL_API_KEY=fc-your-actual-api-key
```

### 3. Create Required Directories

```bash
mkdir -p logs uploads
```

### 4. Deploy with Docker Compose

#### Option A: Full Stack (Backend + Scheduler)

```bash
docker-compose up -d
```

This starts:
- Flask backend API on port 5001
- Daily crawler scheduler (runs at 1 AM)

#### Option B: Scheduler Only

If you're running the backend separately or just want the daily crawler:

```bash
docker-compose -f docker-compose.scheduler.yml up -d
```

#### Option C: Backend Only

```bash
docker-compose up -d backend
```

### 5. Verify Deployment

```bash
# Check running containers
docker ps

# View logs
docker-compose logs -f

# Check backend health
curl http://localhost:5001/api/health

# Check scheduler is running
docker-compose logs scheduler | grep "Starting crawl"
```

## Portainer Deployment

### Deploy via Portainer UI

1. **Access Portainer**
   - Open browser: `http://raspberrypi.local:9000`
   - Or: `http://<pi-ip-address>:9000`

2. **Add New Stack**
   - Go to **Stacks** → **Add stack**
   - Name: `horse-racing-tool`

3. **Web editor method:**
   - Paste contents of `docker-compose.yml`
   - Add environment variables in the UI:
     - `SUPABASE_URL`
     - `SUPABASE_SERVICE_KEY`
     - `FIRECRAWL_API_KEY`
   - Click **Deploy the stack**

4. **Git repository method:**
   - Repository URL: `https://github.com/yourusername/horse-racing-tool`
   - Compose path: `docker-compose.yml`
   - Add environment variables
   - Click **Deploy the stack**

### Build Custom Images in Portainer

1. **Build Backend Image**
   ```bash
   cd /home/pi/horse-racing-tool
   docker build -t horse-racing-backend:latest .
   ```

2. **Build Scheduler Image**
   ```bash
   docker build -f Dockerfile.scheduler -t horse-racing-scheduler:latest .
   ```

3. **Deploy in Portainer**
   - Go to **Containers** → **Add container**
   - Select image: `horse-racing-backend:latest`
   - Configure port mappings, volumes, env vars
   - Click **Deploy**

## Container Configuration Details

### Backend Container

| Setting | Value |
|---------|-------|
| Image | horse-racing-backend:latest |
| Port | 5001:5001 |
| Restart | unless-stopped |
| Memory Limit | 512MB (recommended) |
| Environment | SUPABASE_URL, SUPABASE_SERVICE_KEY, FIRECRAWL_API_KEY, TZ |
| Volumes | ./uploads:/app/uploads, ./logs:/app/logs |

### Scheduler Container

| Setting | Value |
|---------|-------|
| Image | horse-racing-scheduler:latest |
| Restart | unless-stopped |
| Memory Limit | 256MB (recommended) |
| Environment | SUPABASE_URL, SUPABASE_SERVICE_KEY, FIRECRAWL_API_KEY, TZ |
| Volumes | ./logs:/var/log |

## Monitoring and Maintenance

### View Logs

```bash
# All containers
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Scheduler only
docker-compose logs -f scheduler

# Tail last 100 lines
docker-compose logs --tail=100 scheduler
```

### Check Health Status

```bash
# Container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Backend API health
curl http://localhost:5001/api/health

# Check last crawl
docker-compose exec scheduler tail -50 /var/log/horse-racing-crawler.log
```

### Restart Containers

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart scheduler
```

### Update Deployment

```bash
# Pull latest code
cd /home/pi/horse-racing-tool
git pull

# Rebuild and redeploy
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### View Crawler Schedule

```bash
# Check crontab in scheduler container
docker-compose exec scheduler crontab -l
```

## Troubleshooting

### Backend won't start

**Check logs:**
```bash
docker-compose logs backend
```

**Common issues:**
- Missing environment variables → Check `.env` file
- Port 5001 already in use → Change port in docker-compose.yml
- Database connection failed → Verify Supabase credentials

### Scheduler not running crawls

**Check cron is running:**
```bash
docker-compose exec scheduler pgrep cron
```

**Check crontab:**
```bash
docker-compose exec scheduler crontab -l
```

**Manually trigger crawl:**
```bash
docker-compose exec scheduler python3 /app/backend/daily_crawl.py
```

**View crawler logs:**
```bash
docker-compose exec scheduler tail -f /var/log/horse-racing-crawler.log
```

### Containers keep restarting

**Check memory:**
```bash
docker stats
```

**If memory is low:**
- Increase Pi swap space
- Reduce crawler frequency
- Deploy backend and scheduler separately

### Permission issues with volumes

```bash
# Fix permissions
sudo chown -R 1000:1000 /home/pi/horse-racing-tool/logs
sudo chown -R 1000:1000 /home/pi/horse-racing-tool/uploads
```

### Cannot access backend from browser

**Check firewall:**
```bash
sudo ufw status
sudo ufw allow 5001/tcp
```

**Check container networking:**
```bash
docker network inspect horse-racing-tool_horse-racing-network
```

## Resource Usage

Expected resource usage on Raspberry Pi 5:

| Container | CPU (idle) | CPU (active) | RAM | Storage |
|-----------|------------|--------------|-----|---------|
| Backend | 1-5% | 10-30% | 150-300MB | ~500MB |
| Scheduler | <1% | 5-15% | 50-100MB | ~200MB |

**Total:** ~400MB RAM, ~700MB storage

## Security Best Practices

1. **Never commit `.env` file**
   - Always use `.env.example` as template
   - Keep credentials secure

2. **Use service role key for backend**
   - Not anon public key
   - Limit database permissions

3. **Keep containers updated**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

4. **Use secrets in production**
   - Docker secrets or Portainer secrets
   - Don't expose environment variables in Portainer UI

5. **Restrict network access**
   - Use reverse proxy (Nginx/Traefik)
   - Enable HTTPS with Let's Encrypt
   - Restrict API access to local network only

## Frontend Deployment (Optional)

The React frontend can be deployed separately:

### Option 1: Nginx Container

```dockerfile
# Dockerfile.frontend
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Add to docker-compose.yml:
```yaml
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: horse-racing-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - horse-racing-network
```

### Option 2: Serve via Umbrel App

Create Umbrel app manifest and deploy via Umbrel app store.

## Backup and Recovery

### Backup Configuration

```bash
# Backup environment file
cp .env .env.backup

# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# Backup docker compose configs
tar -czf docker-configs-$(date +%Y%m%d).tar.gz \
  docker-compose*.yml Dockerfile* .env.example
```

### Recovery

```bash
# Restore from backup
cp .env.backup .env

# Rebuild containers
docker-compose down -v
docker-compose up -d
```

## Performance Optimization

### For Raspberry Pi 5

1. **Increase swap space:**
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   # Set CONF_SWAPSIZE=2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

2. **Use Docker BuildKit:**
   ```bash
   export DOCKER_BUILDKIT=1
   docker-compose build
   ```

3. **Limit concurrent requests:**
   - Edit `crawl_equibase.py`
   - Reduce number of tracks
   - Add delays between requests

4. **Enable Docker logging limits:**
   ```yaml
   # In docker-compose.yml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

## Next Steps

1. ✅ Deploy to Raspberry Pi 5
2. Test full data pipeline (upload → parse → crawl → display)
3. Set up monitoring (Healthchecks.io, Uptime Kuma)
4. Configure reverse proxy for external access
5. Implement automated backups
6. Add alerting for crawler failures

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Check GitHub issues
4. Verify Firecrawl API credits
5. Test database connection manually

---

**Deployment Status:** Ready for production on Raspberry Pi 5
**Last Updated:** 2026-01-07
