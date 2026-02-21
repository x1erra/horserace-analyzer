# TrackData Backend: Disaster Recovery & Re-deployment Guide

This guide documents the exact steps required to restore the **TrackData Backend** from scratch on a Raspberry Pi or any Ubuntu-based system.

## 📋 Prerequisites
- **Ubuntu/Linux Mint** (specifically Noble/24.04).
- **SSH Access** (e.g., `umbrel@umbrel`).
- **Git Repository URL:** `https://github.com/x1erra/horserace-analyzer.git`

---

## 🛠 Phase 1: Docker & Portainer Setup

### 1. Install Docker
The system uses the modern `docker compose` plugin. Run the existing install script:
```bash
bash ~/horserace-analyzer/install_docker.sh
# IMPORTANT: Log out and back in, OR run 'newgrp docker'
```

### 2. Install Portainer (Optional but Recommended)
To manage containers via a UI:
```bash
sudo docker volume create portainer_data
sudo docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
```
Access at: `https://[PI_IP]:9443`

---

## 📂 Phase 2: Repository & Environment

### 1. Clone the Repo
```bash
git clone https://github.com/x1erra/horserace-analyzer.git ~/horserace-analyzer
cd ~/horserace-analyzer
```

### 2. Configure Supabase (.env)
Create the `.env` file in the root directory. **Without this, the backend will crash.**
```bash
cat <<EOF > .env
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_KEY=your_service_role_key
EOF
```

---

## 🚀 Phase 3: Container Deployment

### 1. Build and Start
Run the standard build command. This ensures all Python dependencies in `Dockerfile` are fresh.
```bash
sudo docker compose up -d --build
```

### 2. Verify Local Startup
Check if the API is responding locally:
```bash
curl http://localhost:5001/api/health
# Expected: {"status": "healthy", "version": "1.0.3"}
```

---

## ☁️ Phase 4: Cloudflare Tunnel Integration

The Cloudflare Tunnel links your public URL (`api.trackdata.live`) to the Pi.

### 1. Retrieve the Token
1. Go to your **Cloudflare Dashboard** -> **Zero Trust** -> **Networks** -> **Tunnels**.
2. Select the **`hr-backend`** tunnel.
3. Click **Configure** -> **Overview**.
4. Copy the long token string after `--token`.

### 2. Configure Umbrel App (or Docker)
If using the Umbrel Cloudflare App:
1. Open the app settings.
2. Paste the **Token**.
3. Ensure the hostname points to: `http://10.0.0.147:5001`.

---

## 🔍 Verification Checklist
- [ ] `docker ps` shows `horse-racing-backend` and `horse-racing-scheduler` as UP.
- [ ] `api.trackdata.live/api/health` returns version `1.0.3`.
- [ ] Dashboard displays 12-hour times and latest racing data.

## 🆘 Common Gotchas
- **Indentation Error:** Python is strict. If editing `backend.py`, use exactly 4 spaces.
- **502 Bad Gateway:** Usually means the backend container crashed. Check logs: `sudo docker logs horse-racing-backend`.
- **404 in Dashboard:** Ensure Cloudflare hostname mapping points to the correct local IP/Port.
