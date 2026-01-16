-- Add selection and bet_cost columns to hranalyzer_bets
ALTER TABLE hranalyzer_bets 
ADD COLUMN IF NOT EXISTS selection JSONB,
ADD COLUMN IF NOT EXISTS bet_cost DECIMAL(10, 2) DEFAULT 0.00;

-- Optional: Add constraint to ensure selection is not null for Box bets? 
--Logic will be handled in application layer.
