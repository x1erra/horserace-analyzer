# Raspberry Pi Deployment Guide

Follow these steps to deploy the live crawler to your Raspberry Pi 5.

## Prerequisites
- Docker and Docker Compose installed on your Pi.
- Access to the Pi via SSH or terminal.

## Steps

1. **Transfer Files**
   Copy the `backend` directory to your Raspberry Pi.
   ```bash
   scp -r backend user@your-pi-ip:~/horse-racing-crawler
   ```
   *(Or if using git, pull the latest changes on your Pi)*

2. **Configure Environment**
   On your Pi, navigate to the folder and create/verify the `.env` file:
   ```bash
   cd ~/horse-racing-crawler/backend
   nano .env
   ```
   Paste your Supabase credentials:
   ```env
   SUPABASE_URL=https://vytyhtddhplcrvvgidyy.supabase.co
   SUPABASE_SERVICE_KEY=your_service_key_here
   ```

3. **Deploy with Docker**
   From the `backend` directory, run:
   ```bash
   docker compose -f docker-compose.scheduler.yml up -d --build
   ```

4. **Verify Deployment**
   Check the logs to ensure it's running:
   ```bash
   docker compose -f docker-compose.scheduler.yml logs -f
   ```
   You should see: "Starting live crawler service..."

## Maintenance
- **Stop**: `docker compose -f docker-compose.scheduler.yml down`
- **Restart**: `docker compose -f docker-compose.scheduler.yml restart`
- **Logs**: `tail -f logs/live_crawler.log` (if volumes mounted)

## Option 2: Portainer (Easiest / UI Way)
If you have Portainer on your Pi and your code is pushed to GitHub/GitLab:

1.  **Push your code**: Ensure your latest changes (including `backend/`) are pushed to your git repository.
2.  **Open Portainer**: Go to your Pi's Portainer UI.
3.  **Add Stack**:
    -   Go to **Stacks** -> **Add stack**.
    -   Name: `horse-racing-crawler`.
    -   Select **Repository** (Git).
    -   Repository URL: Your git repo URL.
    -   Compose path: `backend/docker-compose.scheduler.yml`.
    -   **Environment variables**: Add your secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) in the "Environment variables" section of the UI.
4.  **Deploy**: Click "Deploy the stack".

Portainer will clone your repo, build the image, and start the container. You can view logs directly in Portainer by clicking the container icon -> Logs.
