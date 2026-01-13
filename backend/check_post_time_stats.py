
import os
from supabase_client import get_supabase_client
from datetime import date, timedelta

def check_stats():
    supabase = get_supabase_client()
    
    # Check total races
    res = supabase.table('hranalyzer_races').select('id, post_time, race_date', count='exact').execute()
    total = len(res.data)
    
    with_time = sum(1 for r in res.data if r.get('post_time'))
    without_time = total - with_time
    
    print(f"Total partial-fetched races: {total}")
    print(f"With Post Time: {with_time}")
    print(f"Without Post Time: {without_time}")
    
    # Check specifically for today/tomorrow (upcoming)
    today = date.today()
    upcoming = [r for r in res.data if r['race_date'] >= today.strftime('%Y-%m-%d')]
    up_total = len(upcoming)
    up_with_time = sum(1 for r in upcoming if r.get('post_time'))
    
    print(f"\nUpcoming (Today+): {up_total}")
    print(f"With Post Time: {up_with_time}")
    
    # Sample some with times
    if up_with_time > 0:
        print("\nSample Post Times:")
        for r in upcoming:
            if r.get('post_time'):
                print(f"  {r['race_date']} - {r['post_time']}")
                break

if __name__ == "__main__":
    check_stats()
