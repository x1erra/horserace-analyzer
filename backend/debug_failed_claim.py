
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from supabase_client import get_supabase_client
from crawl_equibase import normalize_name

def check_failed_race():
    supabase = get_supabase_client()
    
    race_id = "abbb7c71-866d-4b4c-898c-93a6567d37a7"
    
    # Get entries
    entries = supabase.table('hranalyzer_race_entries')\
        .select('program_number, hranalyzer_horses(horse_name)')\
        .eq('race_id', race_id)\
        .execute()
        
    print(f"Entries for Race {race_id}:")
    for e in entries.data:
        h_name = e.get('hranalyzer_horses', {}).get('horse_name', '')
        pgm = e.get('program_number')
        print(f" - Pgm: {pgm}, Name: '{h_name}' (Norm: {normalize_name(h_name)})")
        
    print("Target Claim: 'SlenderSlipper'")

if __name__ == "__main__":
    check_failed_race()
