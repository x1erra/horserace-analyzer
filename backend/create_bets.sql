-- Run this in Supabase SQL Editor to enable betting
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
