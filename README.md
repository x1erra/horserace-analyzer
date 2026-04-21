# Horse Racing Data Pipeline

Production-ready horse racing data pipeline that parses Daily Racing Form PDFs and automatically crawls Equibase results to build a comprehensive historical database.

## Features

- 📄 **DRF PDF Parser** - Extract upcoming races from Daily Racing Form PDFs
- 🤖 **Automated Crawler** - Daily Equibase scraping for historical results (100% FREE - no API costs!)
- 🗄️ **Supabase Database** - Cloud-hosted PostgreSQL with real-time capabilities (free tier)
- 🎨 **React Frontend** - Modern UI with Today's Races and Past Results
- 🐳 **Docker Ready** - Optimized for Raspberry Pi 5 deployment
- ⏰ **Scheduled Jobs** - Automated daily data collection
- 💰 **Cost: $0/month** - Runs completely free on your hardware!

## Tech Stack

**Backend:**
- Python 3.13
- Flask REST API
- Supabase (PostgreSQL)
- pdfplumber (PDF parsing - DRF & Equibase)
- requests (HTTP client for Equibase PDFs)

**Frontend:**
- React 19.2.0
- Vite
- React Router
- Tailwind CSS
- Axios

**Infrastructure:**
- Docker & Docker Compose
- Portainer (for Pi 5)
- Cron (scheduler)

## Quick Start

### Local Development

1. **Clone repository**
   ```bash
   git clone https://github.com/yourusername/horse-racing-tool.git
   cd horse-racing-tool
   ```

2. **Set up backend**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   cp .env.example .env
   # Edit .env with your Supabase and Firecrawl credentials

   python backend/backend.py
   ```

3. **Set up frontend**
   ```bash
   npm install
   npm run dev
   ```

4. **Access application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5001

### Docker Deployment (Raspberry Pi 5)

See **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** for complete guide.

```bash
# Quick deploy
cp .env.example .env
nano .env  # Add credentials
docker-compose up -d
```

## Documentation

| Document | Description |
|----------|-------------|
| [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) | Complete Docker deployment guide for Pi 5 |
| [SCHEDULER_QUICKSTART.md](backend/SCHEDULER_QUICKSTART.md) | Quick setup for daily crawler |
| [INTEGRATION_TEST_RESULTS.md](backend/INTEGRATION_TEST_RESULTS.md) | Test results and verification |
| [velvet-hugging-dijkstra.md](~/.claude/plans/) | Complete implementation plan |

## Project Structure

```
horse-racing-tool/
├── backend/
│   ├── backend.py              # Flask API server
│   ├── parse_drf.py            # DRF PDF parser
│   ├── crawl_equibase.py       # Equibase crawler
│   ├── daily_crawl.py          # Scheduled crawler script
│   ├── supabase_client.py      # Database helper
│   ├── db_schema.sql           # Database schema
│   └── crontab                 # Cron schedule
├── src/
│   ├── pages/
│   │   ├── Dashboard.jsx       # Today's races
│   │   ├── Races.jsx           # Browse all races
│   │   ├── RaceDetails.jsx     # Individual race view
│   │   └── Upload.jsx          # DRF PDF upload
│   └── App.jsx                 # Main app component
├── docker-compose.yml          # Full stack deployment
├── docker-compose.scheduler.yml # Scheduler only
├── Dockerfile                  # Backend container
├── Dockerfile.scheduler        # Scheduler container
└── requirements.txt            # Python dependencies
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/todays-races` | GET | Upcoming races for today |
| `/api/past-races` | GET | Historical completed races |
| `/api/race-details/:key` | GET | Full race details with entries |
| `/api/filter-options` | GET | Available tracks, dates, and track summary |
| `/api/claims` | GET | Claims feed with race context |
| `/api/changes` | GET | Normalized scratches and other changes |
| `/api/scratches` | GET | Scratch feed with pagination |
| `/api/horses` | GET | Horse search with aggregate stats |
| `/api/horse/:id` | GET | Stable horse profile by horse ID |
| `/api/uploads` | GET | Recent DRF upload logs |
| `/api/upload-drf` | POST | Upload DRF PDF and queue background parse |
| `/api/uploads/:id/reprocess` | POST | Queue an existing local upload for parsing |
| `/api/uploads/:id` | DELETE | Remove an upload log and unreferenced local PDF |
| `/api/uploads/:filename` | GET | View a locally stored upload PDF |

## MCP Tools

The project also exposes a read-only MCP server for AI agents at `http://<host>:8001/mcp`.

Available MCP tools:

- `get_health`
- `get_feed_freshness`
- `get_tracks`
- `get_recent_uploads`
- `get_filter_options`
- `get_entries`
- `get_results`
- `get_todays_races`
- `get_past_races`
- `get_race_details`
- `get_horses`
- `get_horse_profile`
- `get_scratches`
- `get_changes`
- `get_race_changes`
- `get_claims`

See [backend/MCP_TOOLS.md](/Users/stevendamato/Projects/horserace-analyzer/backend/MCP_TOOLS.md) for usage guidance and how to interpret `get_feed_freshness()`.
See [backend/OPERATOR_RUNBOOK.md](/Users/stevendamato/Projects/horserace-analyzer/backend/OPERATOR_RUNBOOK.md) for deployment, alert, and production triage guidance.

Preferred monitoring entrypoint:
- use `get_health()` or `/api/health` as the one-stop system report
- `get_feed_freshness()` is a backward-compatible alias to the same core health report

## Database Schema

All tables use `hranalyzer_` prefix:

- **hranalyzer_tracks** - Track information
- **hranalyzer_races** - Race metadata and status
- **hranalyzer_horses** - Horse information
- **hranalyzer_jockeys** - Jockey data
- **hranalyzer_trainers** - Trainer data
- **hranalyzer_owners** - Owner data
- **hranalyzer_race_entries** - Junction table (horses ↔ races)
- **hranalyzer_exotic_payouts** - Exacta, trifecta, etc.
- **hranalyzer_upload_logs** - DRF upload tracking
- **hranalyzer_crawl_logs** - Crawler job tracking

## Race Status Flow

Two separate data flows:

### Flow A: Upcoming Races (DRF)
```
User uploads DRF PDF
   → Backend stores PDF on local disk
   → Parser job extracts races in the background
   → Status: "upcoming"
   → Display on "Today's Races"
```

### Flow B: Historical Races (Equibase)
```
Daily crawler runs (1 AM)
   → Fetches previous day results
   → Status: "completed"
   → Display on "Past Races"
```

## Development Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Database setup |
| Phase 2 | ✅ Complete | DRF parser (82 horses from 10 races) |
| Phase 3 | ✅ Complete | Backend API (7 endpoints) |
| Phase 4 | ✅ Complete | Equibase crawler |
| Phase 5 | ✅ Complete | Daily scheduler script |
| Phase 6 | ✅ Complete | Frontend pages |
| Phase 7 | ✅ Complete | Integration testing |
| Phase 8 | ✅ Complete | Docker deployment |

## Configuration

### Environment Variables

Required in `.env` file:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
TRACKDATA_APP_PASSWORD=your-app-password
```

Optional local upload storage settings:

```env
# On this Umbrel/Portainer Docker-in-Docker stack:
# TRACKDATA_UPLOADS_DIR=/data/trackdata/uploads
TRACKDATA_UPLOADS_DIR=./uploads
DRF_PARSE_TIMEOUT_SECONDS=240
DRF_PARSE_WORKERS=1
```

No API keys are needed for web scraping. DRF PDFs are stored locally and served through the backend.

### Crawler Schedule

Default: 1:00 AM daily (configurable in `backend/crontab`)

Target tracks:
- AQU, BEL, CD, DMR, FG, GP, HOU, KEE, SA, SAR, TAM, WO, MD, PRX, PIM

## Testing

Run integration tests:
```bash
# Start servers
python backend/backend.py &
npm run dev &

# Test endpoints
curl http://localhost:5001/api/health
curl http://localhost:5001/api/todays-races
curl http://localhost:5001/api/past-races?limit=10

# Manual crawler test
python backend/daily_crawl.py --date 2026-01-01
```

See [INTEGRATION_TEST_RESULTS.md](backend/INTEGRATION_TEST_RESULTS.md) for detailed results.

## Deployment

### Raspberry Pi 5 with Portainer

```bash
# Fast Portainer path (recommended for day-to-day changes):
# Repo: https://github.com/x1erra/horserace-analyzer.git
# Compose path: docker-compose.portainer.yml
# Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, TRACKDATA_APP_PASSWORD, ALERT_WEBHOOK_URL, BACKEND_PUBLISHED_PORT=5001, MCP_PUBLISHED_PORT=8001
# Recommended upload dir: TRACKDATA_UPLOADS_DIR=/data/trackdata/uploads

# Registry/GHCR path (slower, release-style):
# Compose path: docker-compose.prod.yml
# Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, TRACKDATA_APP_PASSWORD, IMAGE_REGISTRY=ghcr.io/x1erra, IMAGE_TAG=latest
```

Full guide: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)

## Monitoring

- **Logs:** `docker-compose logs -f`
- **Health:** `curl http://localhost:5001/api/health`
- **Crawler:** `docker-compose exec scheduler tail -f /var/log/horse-racing-crawler.log`
- **Database:** Supabase dashboard

## Troubleshooting

### Equibase PDF Parsing Issues
- Crawler uses local Python parsing (no API costs)
- If PDFs fail to parse, check internet connection
- Verify pdfplumber is installed: `pip list | grep pdfplumber`
- Check crawler logs: `docker-compose logs scheduler`

### PDF Upload Fails
- Verify pdfplumber is installed
- Check PDF format (DRF standard format)
- Review logs: `docker-compose logs backend`

### Crawler Not Running
- Check cron: `docker-compose exec scheduler pgrep cron`
- View crontab: `docker-compose exec scheduler crontab -l`
- Manual test: `docker-compose exec scheduler python3 /app/backend/daily_crawl.py`

## Roadmap

### Current (MVP)
- ✅ DRF PDF parsing
- ✅ Equibase historical crawler
- ✅ Basic race display
- ✅ Docker deployment

### Phase 2 (Future)
- [ ] Live odds integration (TVG/TwinSpires)
- [ ] Track conditions and weather
- [ ] Scratches and changes tracking
- [ ] Deep past performance parsing
- [ ] Predictive modeling (ML)
- [ ] Mobile app

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Support

- GitHub Issues: [Create issue](https://github.com/yourusername/horse-racing-tool/issues)
- Documentation: See `/docs` folder
- Email: your-email@example.com

## Acknowledgments

- Daily Racing Form (DRF) for race data format
- Equibase for historical results
- Firecrawl for web scraping API
- Supabase for database hosting

---

**Built for horse racing enthusiasts by data enthusiasts**

Last updated: 2026-01-07
