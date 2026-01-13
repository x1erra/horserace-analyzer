import os
import sys
from supabase_client import get_supabase_client

def check_missing_times():
    try:
        supabase = get_supabase_client()
        
        # Get races where status is completed but final_time is null
        res = supabase.table('hranalyzer_races')\
            .select('race_key, track_code, race_date, race_number, equibase_pdf_url')\
            .eq('race_status', 'completed')\
            .is_('final_time', 'null')\
            .limit(20)\
            .execute()
            
        print(f"Found {len(res.data)} completed races with missing final_time:")
        for r in res.data:
            print(f"- {r['race_key']}: {r['equibase_pdf_url']}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_missing_times()
