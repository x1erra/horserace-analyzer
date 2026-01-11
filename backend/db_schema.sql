-- Horse Racing Analyzer Database Schema
-- All tables prefixed with 'hranalyzer_' to avoid conflicts in shared database
-- Execute this in Supabase SQL Editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================
-- CORE TABLES
-- ==============================================

-- Tracks table
CREATE TABLE IF NOT EXISTS hranalyzer_tracks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  track_code VARCHAR(10) UNIQUE NOT NULL,  -- 'GP', 'AQU', 'SA', etc.
  track_name VARCHAR(255) NOT NULL,
  location VARCHAR(255),
  timezone VARCHAR(50) DEFAULT 'America/New_York',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_tracks_code ON hranalyzer_tracks(track_code);

-- Horses table
CREATE TABLE IF NOT EXISTS hranalyzer_horses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  horse_name VARCHAR(255) NOT NULL,

  -- Optional breeding info (populated from DRF)
  sire VARCHAR(255),
  dam VARCHAR(255),
  foaling_year INTEGER,
  color VARCHAR(50),
  sex CHAR(1),  -- 'C' (colt), 'F' (filly), 'G' (gelding), 'H' (horse), 'M' (mare)

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_horses_name ON hranalyzer_horses(horse_name);

-- Jockeys table
CREATE TABLE IF NOT EXISTS hranalyzer_jockeys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  jockey_name VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_jockeys_name ON hranalyzer_jockeys(jockey_name);

-- Trainers table
CREATE TABLE IF NOT EXISTS hranalyzer_trainers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trainer_name VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_trainers_name ON hranalyzer_trainers(trainer_name);

-- Owners table
CREATE TABLE IF NOT EXISTS hranalyzer_owners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_name VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_owners_name ON hranalyzer_owners(owner_name);

-- ==============================================
-- RACES TABLE (Central table)
-- ==============================================

CREATE TABLE IF NOT EXISTS hranalyzer_races (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Unique identifier: track-date-race_number
  race_key VARCHAR(100) UNIQUE NOT NULL,  -- 'GP-20260101-1'

  -- Basic info
  track_id UUID REFERENCES hranalyzer_tracks(id),
  track_code VARCHAR(10) NOT NULL,
  race_date DATE NOT NULL,
  race_number INTEGER NOT NULL,
  post_time TIME,

  -- Race details
  race_type VARCHAR(100),  -- 'Claiming', 'Allowance', 'Stakes', etc.
  surface VARCHAR(20),     -- 'Dirt', 'Turf', 'Synthetic'
  distance VARCHAR(50),    -- '6 Furlongs', '1 Mile', etc.
  distance_feet INTEGER,   -- Normalized distance in feet
  conditions TEXT,
  purse VARCHAR(50),

  -- Race status and source
  race_status VARCHAR(20) NOT NULL DEFAULT 'upcoming',
  -- 'upcoming' = from DRF, no results yet
  -- 'completed' = results available from Equibase

  data_source VARCHAR(20) NOT NULL,
  -- 'drf' = from uploaded DRF PDF
  -- 'equibase' = from Equibase crawler

  -- Result data (NULL for upcoming races)
  winning_horse_id UUID REFERENCES hranalyzer_horses(id),
  final_time VARCHAR(20),
  fractional_times TEXT,

  -- URLs and metadata
  drf_pdf_path VARCHAR(500),      -- Path to uploaded DRF PDF
  equibase_chart_url VARCHAR(500),
  equibase_pdf_url VARCHAR(500),

  -- Tracking
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  results_fetched_at TIMESTAMPTZ,  -- When Equibase results were added

  CONSTRAINT unique_race UNIQUE(track_code, race_date, race_number)
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_races_status ON hranalyzer_races(race_status);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_races_date ON hranalyzer_races(race_date DESC);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_races_track_date ON hranalyzer_races(track_code, race_date);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_races_key ON hranalyzer_races(race_key);

-- ==============================================
-- RACE ENTRIES TABLE (Junction table)
-- ==============================================

CREATE TABLE IF NOT EXISTS hranalyzer_race_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- References
  race_id UUID NOT NULL REFERENCES hranalyzer_races(id) ON DELETE CASCADE,
  horse_id UUID NOT NULL REFERENCES hranalyzer_horses(id),
  jockey_id UUID REFERENCES hranalyzer_jockeys(id),
  trainer_id UUID REFERENCES hranalyzer_trainers(id),
  owner_id UUID REFERENCES hranalyzer_owners(id),

  -- Entry details (from DRF)
  program_number VARCHAR(10) NOT NULL,  -- '1', '1A', '2', etc.
  post_position INTEGER,
  morning_line_odds VARCHAR(20),  -- '3-1', '5/2', etc.
  weight INTEGER,  -- Weight carried
  medication VARCHAR(100),  -- Lasix, Bute, etc.
  equipment VARCHAR(100),  -- Blinkers, etc.
  claim_price VARCHAR(50),

  -- Pre-race data (from DRF)
  -- Store as JSONB for flexibility - can include speed figures, class ratings, etc.
  drf_past_performances JSONB,  -- Last 10 races, workout data, etc.

  -- Result data (from Equibase, NULL for upcoming races)
  finish_position INTEGER,
  official_position INTEGER,  -- If there's a disqualification
  final_odds VARCHAR(20),  -- Actual odds at post time
  run_comments TEXT,  -- Running line: "Broke alertly, 2p turns, empty late"
  speed_figure INTEGER,

  -- Payout info (for win/place/show)
  win_payout DECIMAL(10, 2),
  place_payout DECIMAL(10, 2),
  show_payout DECIMAL(10, 2),

  -- Tracking
  scratched BOOLEAN DEFAULT FALSE,
  scratch_time TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT unique_race_entry UNIQUE(race_id, program_number)
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_entries_race ON hranalyzer_race_entries(race_id);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_entries_horse ON hranalyzer_race_entries(horse_id);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_entries_finish ON hranalyzer_race_entries(finish_position);

-- ==============================================
-- EXOTIC PAYOUTS TABLE
-- ==============================================

CREATE TABLE IF NOT EXISTS hranalyzer_exotic_payouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id UUID NOT NULL REFERENCES hranalyzer_races(id) ON DELETE CASCADE,

  wager_type VARCHAR(50) NOT NULL,  -- 'Exacta', 'Trifecta', 'Superfecta', 'Daily Double', etc.
  winning_combination VARCHAR(100),  -- '4-2', '4-2-6', etc.
  base_bet VARCHAR(20),  -- '$2', '$1', '$0.50'
  payout DECIMAL(10, 2) NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_exotic_race ON hranalyzer_exotic_payouts(race_id);

-- ==============================================
-- CLAIMS TABLE
-- ==============================================

CREATE TABLE IF NOT EXISTS hranalyzer_claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id UUID NOT NULL REFERENCES hranalyzer_races(id) ON DELETE CASCADE,
  
  -- Horse info
  horse_name VARCHAR(255) NOT NULL,
  program_number VARCHAR(10),
  
  -- Claim info
  new_trainer_name VARCHAR(255),
  new_owner_name VARCHAR(255),
  claim_price DECIMAL(12, 2),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT unique_race_claim UNIQUE(race_id, horse_name)
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_claims_race ON hranalyzer_claims(race_id);

-- ==============================================
-- BETS TABLE
-- ==============================================

CREATE TABLE IF NOT EXISTS hranalyzer_bets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id UUID NOT NULL REFERENCES hranalyzer_races(id) ON DELETE CASCADE,
  
  -- Bet details
  horse_number VARCHAR(10),  -- '1', '1A', etc.
  horse_name VARCHAR(255),   -- Backup/Display
  
  bet_type VARCHAR(50) NOT NULL, -- 'Win', 'Place', 'Show', 'Exacta', 'Trifecta'
  bet_amount DECIMAL(10, 2) NOT NULL DEFAULT 2.00,
  
  -- For exotics
  combination VARCHAR(50), -- e.g. "1-2"
  
  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'Pending', -- 'Pending', 'Win', 'Loss', 'Scratched'
  payout DECIMAL(10, 2) DEFAULT 0.00,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_bets_race ON hranalyzer_bets(race_id);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_bets_status ON hranalyzer_bets(status);

-- ==============================================
-- LOGGING TABLES
-- ==============================================


-- Upload logs table
CREATE TABLE IF NOT EXISTS hranalyzer_upload_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  filename VARCHAR(500) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size INTEGER,

  upload_status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
  -- 'uploaded' -> 'parsing' -> 'completed' or 'failed'

  parse_status VARCHAR(20),
  races_extracted INTEGER DEFAULT 0,
  entries_extracted INTEGER DEFAULT 0,

  error_message TEXT,

  uploaded_at TIMESTAMPTZ DEFAULT NOW(),
  parsed_at TIMESTAMPTZ,

  -- Extracted metadata
  track_code VARCHAR(10),
  race_date DATE
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_upload_date ON hranalyzer_upload_logs(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_upload_status ON hranalyzer_upload_logs(upload_status);

-- Crawl logs table
CREATE TABLE IF NOT EXISTS hranalyzer_crawl_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  crawl_date DATE NOT NULL,  -- Which day's races were crawled
  crawl_type VARCHAR(20) NOT NULL,  -- 'daily_auto', 'manual_trigger', 'retry'

  status VARCHAR(20) NOT NULL DEFAULT 'running',
  -- 'running' -> 'completed' or 'failed'

  tracks_processed INTEGER DEFAULT 0,
  races_updated INTEGER DEFAULT 0,
  entries_updated INTEGER DEFAULT 0,

  error_message TEXT,

  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  duration_seconds INTEGER
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_crawl_date ON hranalyzer_crawl_logs(crawl_date DESC);
CREATE INDEX IF NOT EXISTS idx_hranalyzer_crawl_status ON hranalyzer_crawl_logs(status);

-- ==============================================
-- SEED DATA - Common US Tracks
-- ==============================================

INSERT INTO hranalyzer_tracks (track_code, track_name, location, timezone) VALUES
('AQU', 'Aqueduct', 'Queens, NY', 'America/New_York'),
('BEL', 'Belmont Park', 'Elmont, NY', 'America/New_York'),
('CD', 'Churchill Downs', 'Louisville, KY', 'America/New_York'),
('DMR', 'Del Mar', 'Del Mar, CA', 'America/Los_Angeles'),
('FG', 'Fair Grounds', 'New Orleans, LA', 'America/Chicago'),
('GP', 'Gulfstream Park', 'Hallandale Beach, FL', 'America/New_York'),
('HOU', 'Sam Houston Race Park', 'Houston, TX', 'America/Chicago'),
('KEE', 'Keeneland', 'Lexington, KY', 'America/New_York'),
('SA', 'Santa Anita Park', 'Arcadia, CA', 'America/Los_Angeles'),
('SAR', 'Saratoga', 'Saratoga Springs, NY', 'America/New_York'),
('TAM', 'Tampa Bay Downs', 'Tampa, FL', 'America/New_York'),
('WO', 'Woodbine', 'Toronto, ON', 'America/Toronto'),
('MD', 'Monmouth Park', 'Oceanport, NJ', 'America/New_York'),
('PRX', 'Parx Racing', 'Bensalem, PA', 'America/New_York'),
('PIM', 'Pimlico', 'Baltimore, MD', 'America/New_York')
ON CONFLICT (track_code) DO NOTHING;

-- ==============================================
-- COMPLETE!
-- ==============================================

-- Verify tables were created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE columns.table_name = tables.table_name) as column_count
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'hranalyzer_%'
ORDER BY table_name;
