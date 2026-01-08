# Equibase Crawler Usage Guide

## Overview
The Equibase crawler automatically fetches historical race results from Equibase PDFs and stores them in your Supabase database with `race_status='completed'` and `data_source='equibase'`.

## Usage

### Basic Usage
```bash
# Crawl all common tracks for a specific date
python crawl_equibase.py 2026-01-04

# Crawl specific tracks only
python crawl_equibase.py 2026-01-04 GP,AQU,SA
```

### Via API
```bash
curl -X POST http://localhost:5001/api/trigger-crawl \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-01-04"}'
```

## What It Does

1. **Discovers Races**: For each track, tries races 1-12 to find all races run that day
2. **Extracts Data**: Uses Firecrawl API to extract from Equibase PDF:
   - Race details (type, surface, distance, purse, times)
   - All horses with finish positions
   - Jockeys, trainers, owners
   - Odds and payouts
   - Running comments
   - Exotic wager payouts (Exacta, Trifecta, etc.)
3. **Inserts to Database**: Stores everything in Supabase with proper relationships
4. **Handles Duplicates**: Skips races that already exist in the database

## Features

- **Retry Logic**: 3 attempts with exponential backoff for failed extractions
- **Rate Limiting**: 1 second delay between races to respect API limits
- **Comprehensive Logging**: See exactly what's happening
- **Year Validation**: Currently only supports 2026 data (expandable later)

## Data Flow

```
Equibase PDF URL
  ↓
Firecrawl Extraction
  ↓
Normalize Data
  ↓
Insert to Supabase:
  - hranalyzer_races (status='completed', source='equibase')
  - hranalyzer_horses (get or create)
  - hranalyzer_jockeys (get or create)
  - hranalyzer_trainers (get or create)
  - hranalyzer_race_entries (with results)
  - hranalyzer_exotic_payouts
```

## Example Output

```
INFO:__main__:Starting crawl for 2026-01-04
INFO:__main__:Tracks to check: GP, AQU, SA

INFO:__main__:Processing track: GP
INFO:__main__:Extracting data from https://www.equibase.com/static/chart/pdf/GP010426USA1.pdf
INFO:__main__:Inserted race GP-20260104-1
INFO:__main__:Inserted 9 entries for race GP-20260104-1
...

INFO:__main__:Crawl complete!
INFO:__main__:Tracks processed: 3
INFO:__main__:Races found: 28
INFO:__main__:Races inserted: 28
```

## Cost Considerations

- Firecrawl API charges per extraction
- Each race = 1 API call
- A typical day across 15 tracks with 10 races each = 150 API calls
- Plan accordingly with your Firecrawl subscription

## Limitations (Current)

- Only 2026 data (expand `crawl_historical_races()` function to support other years)
- Checks fixed set of tracks (modify `COMMON_TRACKS` list to add more)
- No automatic scheduling (see daily_crawl.py for scheduled runs)

## Troubleshooting

**"FIRECRAWL_API_KEY not set"**
- Make sure `.env` file has `FIRECRAWL_API_KEY=your-key-here`

**"Track XYZ not found in database"**
- Track needs to be added to `hranalyzer_tracks` table first
- Check `db_schema.sql` for seeded tracks

**"Only 2026 data supported"**
- Modify line 351 in `crawl_equibase.py` to allow other years

**Race extraction fails**
- Check if PDF URL is correct (race might not exist)
- Firecrawl might be having issues
- Check your API quota

## Next Steps

See `daily_crawl.py` for automatic daily crawling setup.
