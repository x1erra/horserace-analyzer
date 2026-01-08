# Quick Start - Deploy in 15 Minutes

**The fastest way to get your horse racing pipeline running on Raspberry Pi 5.**

---

## Prerequisites

- Raspberry Pi 5 with Docker installed
- Supabase account and project created
- Your Supabase URL and Service Role Key

---

## Step 1: Transfer Code (2 minutes)

```bash
# On your Mac
cd ~/Projects
rsync -avz --exclude 'node_modules' --exclude 'venv' --exclude '.git' \
  horse-racing-tool/ pi@raspberrypi.local:~/horse-racing-tool/
```

---

## Step 2: Deploy Database (1 minute)

1. Go to https://supabase.com/dashboard
2. Open your project → SQL Editor → New Query
3. Copy/paste contents of `backend/db_schema.sql`
4. Click **Run**

---

## Step 3: Configure (1 minute)

```bash
# SSH to Pi
ssh pi@raspberrypi.local
cd ~/horse-racing-tool

# Create .env file
cp .env.example .env
nano .env
```

**Edit to add:**
```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_KEY=YOUR_SERVICE_KEY
```

Save: `Ctrl+X`, `Y`, `Enter`

---

## Step 4: Create Directories (30 seconds)

```bash
mkdir -p logs uploads
chmod 755 logs uploads
```

---

## Step 5: Build & Deploy (5-10 minutes)

```bash
# Build images
docker build -t horse-racing-backend:latest .
docker build -f Dockerfile.scheduler -t horse-racing-scheduler:latest .

# Start containers
docker-compose up -d

# Wait 10 seconds
sleep 10
```

---

## Step 6: Verify (1 minute)

```bash
# Check containers
docker-compose ps

# Test API
curl http://localhost:5001/api/health

# Should return: {"status":"ok"}
```

---

## ✅ Done!

Your system is now running!

**What happens next:**
- Crawler runs automatically at 1:00 AM every night
- Collects previous day's race results from Equibase
- Stores everything in your Supabase database
- **Cost: $0/month**

---

## Daily Commands

```bash
# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Restart services
docker-compose restart

# Manual crawler run
docker-compose exec scheduler python3 /app/backend/daily_crawl.py

# Check crawler ran at 1 AM
docker-compose exec scheduler tail -100 /var/log/horse-racing-crawler.log | grep "Crawl Summary"
```

---

## Upload DRF PDF

```bash
# Copy PDF to Pi
scp ~/Downloads/drf.pdf pi@raspberrypi.local:~/

# Upload
curl -X POST -F "file=@drf.pdf" http://localhost:5001/api/upload-drf
```

---

## Need More Help?

- **Full guide:** `DEPLOY_NOW.md` (step-by-step with troubleshooting)
- **Docker reference:** `DOCKER_DEPLOYMENT.md`
- **Free operation details:** `FREE_OPERATION_UPDATE.md`

---

**That's it! You're done in 15 minutes.** 🎉
