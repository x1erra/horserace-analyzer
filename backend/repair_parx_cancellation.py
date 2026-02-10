
from supabase_client import get_supabase_client
from datetime import date

def repair_parx():
    supabase = get_supabase_client()
    
    # Parx Racing (PRX) was cancelled on Feb 9, 2026.
    # The user reported 1 race still showing as upcoming.
    
    dates = ['2026-02-09', '2026-02-10']
    
    for d in dates:
        print(f"\n--- Repairing Parx Racing on {d} ---")
        
        # Find Parx races for this date that are 'upcoming' 
        # and truly should be cancelled (since ALL PRX races were cancelled on Feb 9).
        # On Feb 10, they might also be cancelled or just need status alignment.
        
        res = supabase.table('hranalyzer_races')\
            .select('id, race_number, race_status')\
            .eq('track_code', 'PRX')\
            .eq('race_date', d)\
            .execute()
            
        if not res.data:
            print(f"No races found for {d}")
            continue
            
        for r in res.data:
            if r['race_status'] == 'upcoming':
                print(f"Fixing Race {r['race_number']}: 'upcoming' -> 'cancelled'")
                supabase.table('hranalyzer_races')\
                    .update({
                        'race_status': 'cancelled',
                        'is_cancelled': True,
                        'cancellation_reason': 'Manual repair for missed cancellation update'
                    })\
                    .eq('id', r['id'])\
                    .execute()
            else:
                print(f"Race {r['race_number']} is already {r['race_status']}.")

if __name__ == "__main__":
    repair_parx()
