import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict

# Add backend directory to path to import from crawl_equibase
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client
from dotenv import load_dotenv

# Import necessary functions from crawler
from crawl_equibase import (
    download_pdf,
    parse_equibase_pdf,
    insert_claim,
    build_equibase_url
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials not found in .env")
    sys.exit(1)

def backfill_claims(start_date: str, end_date: str):
    """
    Backfill claims for races within a date range.
    """
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    logger.info(f"Starting claims backfill from {start_date} to {end_date}")

    # Query races in range
    try:
        response = supabase.table('hranalyzer_races') \
            .select('id, race_date, track_code, race_number, equibase_chart_url, equibase_pdf_url') \
            .gte('race_date', start_date) \
            .lte('race_date', end_date) \
            .order('race_date') \
            .execute()
        
        races = response.data
        logger.info(f"Found {len(races)} races to process")
        
    except Exception as e:
        logger.error(f"Error fetching races: {e}")
        return

    processed_count = 0
    claims_found = 0
    errors = 0

    for race in races:
        race_id = race['id']
        # Try to get PDF URL from DB, otherwise reconstruct it
        url = race.get('equibase_pdf_url')
        race_str = f"{race['race_date']} {race['track_code']} R{race['race_number']}"

        if not url:
            # Fallback: Reconstruct URL
            try:
                r_date = datetime.strptime(race['race_date'], '%Y-%m-%d').date()
                url = build_equibase_url(race['track_code'], r_date, race['race_number'])
                logger.info(f"Reconstructed URL for {race_str}: {url}")
            except Exception as e:
                logger.warning(f"Could not key URL for {race_str}: {e}")
                continue


        try:
            # Download PDF
            # logger.info(f"Processing {race_str}...")
            pdf_bytes = download_pdf(url)
            if not pdf_bytes:
                logger.error(f"Failed to download PDF for {race_str}")
                errors += 1
                continue

            # Parse PDF (extracts text and parses data)
            race_data = parse_equibase_pdf(pdf_bytes)
            
            if not race_data:
                logger.error(f"Failed to parse PDF for {race_str}")
                errors += 1
                continue
                
            claims = race_data.get('claims', [])

            if claims:
                logger.info(f"Found {len(claims)} claims in {race_str}")
                claims_found += len(claims)
                
                # Insert claims
                for claim in claims:
                    insert_claim(supabase, race_id, claim)
            
            processed_count += 1


        except Exception as e:
            logger.error(f"Error processing {race_str}: {e}")
            errors += 1

    logger.info("="*50)
    logger.info(f"Backfill Complete")
    logger.info(f"Races Processed: {processed_count}")
    logger.info(f"Claims Found/Inserted: {claims_found}")
    logger.info(f"Errors: {errors}")
    logger.info("="*50)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python backfill_claims.py <start_date> <end_date>")
        print("Example: python backfill_claims.py 2024-01-01 2024-01-31")
        sys.exit(1)
        
    start = sys.argv[1]
    end = sys.argv[2]
    
    backfill_claims(start, end)
