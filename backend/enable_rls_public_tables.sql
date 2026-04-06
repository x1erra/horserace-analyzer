-- TrackData Supabase hardening
--
-- This project uses Supabase from the backend only via the service-role key.
-- The React frontend does not query Supabase directly.
--
-- Goal:
-- - enable RLS on sensitive/public tables flagged by Supabase Advisor
-- - revoke anon/authenticated access so browser-side roles cannot read/write them
-- - keep backend service-role access working unchanged

begin;

-- Bets and bankroll data are sensitive and should never be readable directly
-- by anon/authenticated roles.
alter table if exists public.hranalyzer_bets enable row level security;
alter table if exists public.hranalyzer_wallets enable row level security;
alter table if exists public.hranalyzer_transactions enable row level security;

-- Claims and changes are operational data. The app still serves them through
-- the Flask API, so direct public table access is unnecessary.
alter table if exists public.hranalyzer_claims enable row level security;
alter table if exists public.hranalyzer_changes enable row level security;

-- Remove any broad direct table privileges from client-facing roles.
revoke all on table public.hranalyzer_bets from anon, authenticated;
revoke all on table public.hranalyzer_wallets from anon, authenticated;
revoke all on table public.hranalyzer_transactions from anon, authenticated;
revoke all on table public.hranalyzer_claims from anon, authenticated;
revoke all on table public.hranalyzer_changes from anon, authenticated;

-- No RLS policies are added intentionally.
-- That means anon/authenticated roles cannot access these tables directly.
-- The backend continues to work through the service-role key.

commit;

-- Verification queries you can run afterward:
-- select schemaname, tablename, rowsecurity
-- from pg_tables
-- where schemaname = 'public'
--   and tablename in (
--     'hranalyzer_bets',
--     'hranalyzer_wallets',
--     'hranalyzer_transactions',
--     'hranalyzer_claims',
--     'hranalyzer_changes'
--   )
-- order by tablename;
