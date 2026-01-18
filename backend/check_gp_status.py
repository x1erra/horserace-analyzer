
import logging
import sys
import os
from datetime import date
from supabase_client import get_supabase_client
from crawl_scratches import fetch_rss_feed, parse_rss_changes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_gp_status():
    track_code = 'GP'
    race_date = date.today()
    race_number = 2
    race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{race_number}"
    
    logger.info(f"Checking status for {race_key}...")
    
    # 1. Check DB
    supabase = get_supabase_client()
    res = supabase.table('hranalyzer_races').select('*').eq('race_key', race_key).execute()
    
    if res.data:
        race = res.data[0]
        logger.info(f"DB Status: {race.get('race_status')}")
        logger.info(f"DB Record: {race}")
    else:
        logger.warning("Race not found in DB!")
        return

    # Check Changes Table
    changes_res = supabase.table('hranalyzer_changes').select('*').eq('race_id', race['id']).execute()
    if changes_res.data:
        logger.info(f"DB Changes ({len(changes_res.data)}):")
        for c in changes_res.data:
             logger.info(f" - {c['change_type']}: {c['description']}")
    else:
        logger.info("No changes records in DB.")


    # 2. Check RSS Source
    logger.info(f"Fetching RSS for {track_code}...")
    xml = fetch_rss_feed(track_code)
    
    if xml:
        logger.info("RSS Feed Fetched successfully.")
        changes = parse_rss_changes(xml, track_code)
        
        # Filter for Race 2
        r2_changes = [c for c in changes if c['race_number'] == race_number]
        
        if r2_changes:
            logger.info(f"Found RSS changes for Race 2: {r2_changes}")
        else:
            logger.info("No changes found in RSS for Race 2.")
            
        print("\n--- RAW XML SEGMENT FOR RACE 2 (if any) ---")
        # dump simplified view
        for line in xml.split('\n'):
             if "Race 2" in line or "Race 02" in line:
                 print(line.strip())
    else:
        logger.warning("Failed to fetch RSS feed.")

    # 3. Check HTML Source
    logger.info("Fetching HTML Late Changes for GP...")
    from crawl_scratches import fetch_static_page, parse_track_changes
    html_url = "https://www.equibase.com/static/latechanges/html/latechangesGP-USA.html"
    html = fetch_static_page(html_url)
    
    if html:
        logger.info("HTML Page Fetched.")
        html_changes = parse_track_changes(html, track_code)
        r2_html = [c for c in html_changes if c['race_number'] == race_number]
        if r2_html:
            logger.info(f"Found HTML changes for Race 2: {r2_html}")
        else:
            logger.info("No changes found in HTML for Race 2.")
            
        with open("debug_gp_html.html", "w", encoding="utf-8") as f:
            f.write(html)
            
    else:
        logger.warning("Failed to fetch HTML page.")

if __name__ == "__main__":
    check_gp_status()
