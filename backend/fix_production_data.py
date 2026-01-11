import os
import sys
from datetime import date, datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from crawl_equibase import download_pdf, parse_race_chart_text

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def fix_historical_races(target_dates):
    for target_date in target_dates:
        print(f"\nProcessing date: {target_date}")
        
        # Get races for this date
        res = supabase.table('hranalyzer_races').select('*').eq('race_date', target_date).execute()
        races = res.data
        
        print(f"Found {len(races)} races")
        
        for race in races:
            track_code = race['track_code']
            race_number = race['race_number']
            race_id = race['id']
            
            # 1. Update Chart URL (Static PDF format)
            # Use datetime object for formatting
            dt = datetime.strptime(target_date, '%Y-%m-%d')
            new_chart_url = f"https://www.equibase.com/static/chart/pdf/{track_code}{dt.strftime('%m%d%y')}USA{race_number}.pdf"
            
            # 2. Extract Final Time if N/A
            final_time = race.get('final_time')
            if not final_time or final_time == 'N/A' or final_time == 'None':
                print(f"Extracting time for {track_code} Race {race_number}...")
                pdf_url = f"https://www.equibase.com/static/chart/pdf/{track_code}{dt.strftime('%m%d%y')}USA{race_number}.pdf"
                pdf_bytes = download_pdf(pdf_url)
                if pdf_bytes:
                    import pdfplumber
                    from io import BytesIO
                    try:
                        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                            text = pdf.pages[0].extract_text()
                            parsed_data = parse_race_chart_text(text)
                            extracted_time = parsed_data.get('final_time')
                            if extracted_time:
                                final_time = extracted_time
                                print(f"  Extracted Time: {final_time}")
                    except Exception as e:
                        print(f"  Error parsing PDF: {e}")
                else:
                    print(f"  Failed to download PDF: {pdf_url}")

            # Update DB
            update_data = {
                'equibase_chart_url': new_chart_url,
                'final_time': final_time if final_time else 'N/A'
            }
            
            supabase.table('hranalyzer_races').update(update_data).eq('id', race_id).execute()
            print(f"Updated {track_code} Race {race_number}")

if __name__ == "__main__":
    fix_historical_races(['2026-01-01', '2026-01-04'])
