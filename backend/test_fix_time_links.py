import os
import sys
from datetime import date
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.crawl_equibase import extract_race_from_pdf, build_equibase_url

def test_extraction():
    track_code = "FG"
    race_date = date(2026, 1, 4)
    race_number = 1
    
    pdf_url = build_equibase_url(track_code, race_date, race_number)
    print(f"Testing extraction from: {pdf_url}")
    
    race_data = extract_race_from_pdf(pdf_url)
    
    if race_data:
        print(f"Extraction successful!")
        print(f"Track: {race_data.get('track_name')}")
        print(f"Final Time: {race_data.get('final_time')}")
        
        # Check URL generation (we need to check how it will be saved in insert_race_to_db)
        chart_url = f"https://www.equibase.com/static/chart/pdf/{track_code}{race_date.strftime('%m%d%y')}USA{race_number}.pdf"
        print(f"Generated Chart URL: {chart_url}")
    else:
        print("Extraction failed.")

if __name__ == "__main__":
    test_extraction()
