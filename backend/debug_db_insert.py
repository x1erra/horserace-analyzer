
import sys
import logging
import re
from datetime import date
from supabase_client import get_supabase_client
from crawl_equibase import insert_race_to_db, parse_race_chart_text, parse_horses_from_text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_db_insert():
    try:
        print("Connecting to Supabase...")
        supabase = get_supabase_client()
        
        with open("debug_text.txt", "r", encoding="utf-8") as f:
            text = f.read()

        race_data = parse_race_chart_text(text)
        race_data['horses'] = parse_horses_from_text(text)
        
        # Hardcode track and date from the PDF we know
        track_code = 'AQU'
        race_date = date(2026, 1, 11)
        
        print(f"Attempting to insert race for {track_code} on {race_date}...")
        success = insert_race_to_db(supabase, track_code, race_date, race_data)
        
        if success:
            print("Successfully inserted race to DB!")
        else:
            print("Failed to insert race to DB.")

    except Exception as e:
        print(f"Exception during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_db_insert()
