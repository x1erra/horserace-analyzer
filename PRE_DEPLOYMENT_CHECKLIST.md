# Pre-Deployment Checklist

**Complete this checklist before deploying to ensure smooth installation.**

---

## Hardware & Network

- [ ] Raspberry Pi 5 is powered on
- [ ] Pi is connected to network (ethernet or WiFi)
- [ ] Pi has stable internet connection
- [ ] You can SSH to Pi: `ssh pi@raspberrypi.local`
- [ ] Pi has at least 5GB free disk space: `df -h`

---

## Software Prerequisites

- [ ] Docker is installed: `ssh pi@raspberrypi.local "docker --version"`
- [ ] Docker Compose is installed: `ssh pi@raspberrypi.local "docker-compose --version"`
- [ ] Git is installed (if using git method): `ssh pi@raspberrypi.local "git --version"`

**If not installed, install Docker:**
```bash
ssh pi@raspberrypi.local
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in
```

---

## Supabase Setup

- [ ] Supabase account created at https://supabase.com
- [ ] New project created in Supabase
- [ ] Project is active (not paused)

**Get your credentials:**
- [ ] **Project URL** copied (Settings → API → Config → Project URL)
  - Format: `https://abcdefgh.supabase.co`
- [ ] **Service Role Key** copied (Settings → API → Project API keys → service_role)
  - Format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
  - ⚠️ **Important:** Use `service_role` key, NOT `anon` key!

---

## Code Transfer Method

Choose ONE method:

### Option A: Git (Recommended)
- [ ] Code is committed to GitHub/GitLab
- [ ] Repository is accessible (public or SSH key configured)
- [ ] You know your repository URL

### Option B: Rsync
- [ ] You can rsync from Mac to Pi: `rsync --version`
- [ ] SSH access to Pi working
- [ ] Project folder is at `~/Projects/horse-racing-tool` on Mac

---

## Database Schema Ready

- [ ] You have `backend/db_schema.sql` file
- [ ] File is readable: `cat backend/db_schema.sql | head`
- [ ] File contains `CREATE TABLE hranalyzer_tracks` and 9 other tables

---

## Environment File Ready

- [ ] `.env.example` file exists
- [ ] You know where to find it: `backend/.env.example` or root `.env.example`
- [ ] You have a text editor ready (nano, vim, or VSCode remote)

---

## Optional: Test Deployment Locally First

Before deploying to Pi, you can test on your Mac:

- [ ] Build backend locally: `docker build -t test-backend .`
- [ ] Build scheduler locally: `docker build -f Dockerfile.scheduler -t test-scheduler .`
- [ ] Both builds succeed without errors

---

## Time & Availability

- [ ] You have 30-60 minutes of uninterrupted time
- [ ] Pi will stay powered on during deployment
- [ ] Network connection is stable (no pending router reboots, etc.)

---

## Documentation Ready

Have these files open/accessible:

- [ ] `DEPLOY_NOW.md` - Main deployment guide
- [ ] `QUICK_START.md` - Quick reference
- [ ] `DOCKER_DEPLOYMENT.md` - Detailed troubleshooting
- [ ] Your Supabase credentials (URL + Service Key) in notepad/text file

---

## Post-Deployment Access

Plan how you'll access the system:

- [ ] Pi's local IP address known (for API access from Mac)
- [ ] Or: Pi's hostname resolves: `ping raspberrypi.local`
- [ ] Browser ready for testing API endpoints

---

## Backup Plan

- [ ] Pi's current state is backed up (if important)
- [ ] Or: Pi is dedicated to this project (nothing to lose)
- [ ] You know how to stop containers if needed: `docker-compose down`

---

## Questions Answered

Before starting, make sure you know:

- [ ] Where the project will be located on Pi (`/home/pi/horse-racing-tool`)
- [ ] What port the API will run on (`5001`)
- [ ] When the crawler will run (`1:00 AM daily`)
- [ ] How to view logs (`docker-compose logs -f`)

---

## Ready to Deploy?

✅ **All items checked above?**

👉 **Start deployment with:** `DEPLOY_NOW.md` or `QUICK_START.md`

⏱️ **Estimated time:** 15-30 minutes (first time), 5-10 minutes (subsequent deploys)

💰 **Monthly cost after deployment:** $0

---

## Not Ready Yet?

**Missing Docker?**
```bash
ssh pi@raspberrypi.local
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Missing Supabase credentials?**
1. Go to https://supabase.com
2. Create account
3. Create new project
4. Wait for project to provision (2-3 minutes)
5. Go to Settings → API
6. Copy Project URL and service_role key

**Missing SSH access?**
```bash
# Enable SSH on Pi
# Put a file named 'ssh' in /boot partition
# Or use Raspberry Pi Imager to enable SSH

# Test from Mac
ssh pi@raspberrypi.local
# Default password is usually 'raspberry'
```

**Code not ready?**
- Review `PROJECT_COMPLETION_SUMMARY.md` to see what's implemented
- Check `README.md` for project overview
- All code is in current directory

---

## Emergency Rollback

If deployment fails, you can easily roll back:

```bash
# Stop containers
docker-compose down

# Remove containers
docker-compose down -v

# Remove images
docker rmi horse-racing-backend horse-racing-scheduler

# Start over from step 1
```

---

## Success Criteria

After deployment, you should be able to:

✅ See two running containers: `docker-compose ps`
✅ Get `{"status":"ok"}` from: `curl http://localhost:5001/api/health`
✅ View logs without errors: `docker-compose logs`
✅ Run manual crawler: `docker-compose exec scheduler python3 /app/backend/daily_crawl.py`
✅ See cron scheduled: `docker-compose exec scheduler crontab -l`

---

**Ready? Let's deploy!** → Start with `DEPLOY_NOW.md` or `QUICK_START.md`
