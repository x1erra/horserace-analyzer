
-- Add is_cancelled flag to races table
-- This allows us to track cancellation separately from the lifecycle status (upcoming/completed)
-- and recover gracefully if a race is incorrectly marked as cancelled.

ALTER TABLE hranalyzer_races 
ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT FALSE;

ALTER TABLE hranalyzer_races 
ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_hranalyzer_races_cancelled ON hranalyzer_races(is_cancelled);
