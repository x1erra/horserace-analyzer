"""Check status of claims program numbers"""
import sys
sys.path.insert(0, '.')

from supabase_client import get_supabase_client

supabase = get_supabase_client()

# Check total claims
total = supabase.table('hranalyzer_claims').select('id', count='exact').execute()
print(f"Total claims in database: {total.count}")

# Check claims with program numbers
with_pgm = supabase.table('hranalyzer_claims').select('id', count='exact').not_.is_('program_number', 'null').execute()
print(f"Claims with program_number: {with_pgm.count}")

# Check claims without program numbers
without = supabase.table('hranalyzer_claims').select('horse_name, race_id').is_('program_number', 'null').execute()
print(f"Claims WITHOUT program_number: {len(without.data)}")

if without.data:
    print("\nMissing program numbers:")
    for c in without.data:
        print(f"  - {c['horse_name']} (Race: {c['race_id'][:8]}...)")
else:
    print("\n✓ All claims have program numbers!")
