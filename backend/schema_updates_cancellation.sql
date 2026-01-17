-- Create hranalyzer_changes table if it doesn't exist
CREATE TABLE IF NOT EXISTS hranalyzer_changes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  race_id UUID NOT NULL REFERENCES hranalyzer_races(id) ON DELETE CASCADE,
  entry_id UUID REFERENCES hranalyzer_race_entries(id) ON DELETE CASCADE, -- Nullable for race-wide changes
  
  change_type VARCHAR(50) NOT NULL, -- 'Scratch', 'Jockey Change', 'Race Cancelled', 'Surface Change'
  description TEXT,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Prevent duplicates
  -- Prevent duplicates (Strict)
  CONSTRAINT unique_race_entry_change UNIQUE (race_id, entry_id, change_type)
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_changes_race ON hranalyzer_changes(race_id);

-- No change needed for race_status as it is VARCHAR, but we will use 'cancelled' as value.
