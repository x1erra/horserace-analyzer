
import os
import sys
from supabase_client import get_supabase_client
from dotenv import load_dotenv

def fix_and_scan():
    load_dotenv()
    client = get_supabase_client()
    
    # --- PART 1: FIX "Stayed in for Half" ---
    print("--- PART 1: Fixing 'Stayed in for Half' ---")
    
    # IDs from previous debug output
    horse_id_target = '86ec9a6d-f5fc-4d3d-affa-4f2eaf77e73a'
    race_id_target = 'adf4e0ee-d868-48a0-a936-3d060d3e4808'
    
    print(f"Updating program_number to '8' for horse {horse_id_target} in race {race_id_target}...")
    
    try:
        update_response = client.table('hranalyzer_race_entries')\
            .update({'program_number': '8'})\
            .eq('race_id', race_id_target)\
            .eq('horse_id', horse_id_target)\
            .execute()
            
        if update_response.data:
            print("Successfully updated record:")
            print(update_response.data[0])
        else:
            print("Update returned no data. Check if record exists.")
    except Exception as e:
        print(f"Error updating record: {e}")

    # --- PART 2: SCAN FOR OTHERS ---
    print("\n--- PART 2: Scanning for other missing program numbers ---")
    
    try:
        # Fetch entries with empty or null program_number
        # Note: Supabase/PostgREST filtering for empty string or null might need two queries or an OR filter.
        # Simple approach: Fetch all where program_number is null OR program_number is ''
        
        # 1. Check for NULL
        print("Checking for NULL program_number...")
        null_response = client.table('hranalyzer_race_entries')\
            .select('*, hranalyzer_races(race_date, track_code, race_number, race_status), hranalyzer_horses(horse_name)')\
            .is_('program_number', 'null')\
            .execute()
            
        # 2. Check for Empty String
        print("Checking for Empty String program_number...")
        empty_response = client.table('hranalyzer_race_entries')\
            .select('*, hranalyzer_races(race_date, track_code, race_number, race_status), hranalyzer_horses(horse_name)')\
            .eq('program_number', '')\
            .execute()
            
        all_issues = (null_response.data or []) + (empty_response.data or [])
        
        if not all_issues:
            print("No other issues found!")
            return

        print(f"\nFound {len(all_issues)} potentially problematic entries.")
        print(f"{'Date':<12} {'Track':<5} {'Race':<5} {'Horse':<25} {'Status':<10} {'ID'}")
        print("-" * 80)
        
        count = 0
        for entry in all_issues:
            race = entry.get('hranalyzer_races')
            horse = entry.get('hranalyzer_horses')
            
            if not race or not horse:
                continue

            # Optional: Filter out very old races if needed, but user asked for "in the db"
            # Maybe filter out scratched horses if they often lose numbers? (Though they usually keep them)
             
            print(f"{race['race_date']:<12} {race['track_code']:<5} {str(race['race_number']):<5} {horse['horse_name']:<25} {race['race_status']:<10} {entry['id']}")
            count += 1
            if count >= 50:
                print("... (Simulated limit of 50 for display) ...")
                break
                
    except Exception as e:
        print(f"Error scanning: {e}")

if __name__ == "__main__":
    fix_and_scan()
