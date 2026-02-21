# TrackData Backend: Troubleshooting Guide

## 🔴 502 Bad Gateway / CORS Errors on `api.trackdata.live`

**Symptoms:**
- Cloudflare shows "Host: Error" on the 502 page
- Browser console shows `Access-Control-Allow-Origin` / CORS errors
- `GET https://api.trackdata.live/api/health` returns 502
- Portainer logs show `127.0.0.1` healthchecks succeeding (this is normal — it's the internal Docker healthcheck)

**Root Cause:**
Port mapping mismatch. The Cloudflare Tunnel points to `http://10.0.0.147:5001`, but the container may have been restarted (e.g. by an AI agent or Portainer) with the wrong host port (e.g. `5002:5001` instead of `5001:5001`).

**How to Diagnose:**
1. Check Portainer → Containers → `horse-racing-backend` → **Published Ports** column
2. It should read `5001:5001`. If it reads `5002:5001` or anything else, that's the problem.
3. The Cloudflare Tunnel (Umbrel app at `10.0.0.147:4499`) should show the route as `http://10.0.0.147:5001`

**Fix (confirmed working 2026-02-21):**

```bash
ssh umbrel@umbrel
cd ~/horserace-analyzer

# Force remove the orphaned/misconfigured containers
sudo docker rm -f horse-racing-backend horse-racing-scheduler

# Redeploy from the correct docker-compose.yml (has 5001:5001)
sudo docker compose up -d

# Verify
curl http://localhost:5001/api/health
curl https://api.trackdata.live/api/health
```

**Why this happens:**
- If something (Portainer UI, an AI agent, or a manual `docker run`) restarts the container outside of `docker compose`, it may assign a different host port.
- Always redeploy via `docker compose up -d` from `~/horserace-analyzer` to ensure the correct port mapping from `docker-compose.yml` is used.

---

## ⚠️ Container Name Conflict on `docker compose up`

**Symptom:**
```
Error: The container name "/horse-racing-backend" is already in use by container "abc123..."
```

**Fix:**
```bash
sudo docker rm -f horse-racing-backend horse-racing-scheduler
sudo docker compose up -d
```

---

## 📌 Key Infrastructure Facts

| Component | Value |
|-----------|-------|
| Pi IP | `10.0.0.147` |
| Backend host port | `5001` |
| Backend container port | `5001` |
| Cloudflare Tunnel route | `api.trackdata.live` → `http://10.0.0.147:5001` |
| Portainer | `https://10.0.0.147:9443` |
| Umbrel Cloudflare app | `http://10.0.0.147:4499` |
| Compose file | `~/horserace-analyzer/docker-compose.yml` |

## 🛑 Important Rule

> **NEVER restart containers via Portainer UI or `docker run` directly.** Always use `docker compose up -d` from `~/horserace-analyzer` to preserve correct port mappings and network config.
