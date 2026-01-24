-- Wallet / Bankroll Table
-- For now, we assume a single-player mode (default user)
-- If we add Auth later, we will add 'user_id' column

CREATE TABLE IF NOT EXISTS hranalyzer_wallets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- For single player, we can just enforce one row or use a fixed ID/Name
  -- We'll use a unique constraint on a 'user_ref' identifier
  user_ref VARCHAR(50) UNIQUE NOT NULL DEFAULT 'default_user',
  
  balance DECIMAL(12, 2) NOT NULL DEFAULT 1000.00,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transaction Log (Optional but good for audit)
CREATE TABLE IF NOT EXISTS hranalyzer_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES hranalyzer_wallets(id),
    
    amount DECIMAL(12, 2) NOT NULL, -- Positive for deposit/win, Negative for bet/withdraw
    transaction_type VARCHAR(50) NOT NULL, -- 'Deposit', 'Withdraw', 'Bet', 'Payout', 'Refund'
    reference_id UUID, -- Link to bet_id or other source
    description TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hranalyzer_trans_wallet ON hranalyzer_transactions(wallet_id);

-- Insert default user if not exists
INSERT INTO hranalyzer_wallets (user_ref, balance)
VALUES ('default_user', 1000.00)
ON CONFLICT (user_ref) DO NOTHING;
