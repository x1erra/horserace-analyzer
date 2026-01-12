import time
import logging
import signal
import sys
import os
from datetime import datetime, date, timedelta
import zoneinfo
from crawl_equibase import crawl_historical_races, COMMON_TRACKS
from crawl_entries import crawl_entries

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('live_crawler.log')
    ]
)
logger = logging.getLogger("LiveCrawler")

# Constants
EST = zoneinfo.ZoneInfo("America/New_York")
START_HOUR = 0
END_HOUR = 23 # Run 24/7 to ensure morning races are captured

def run_crawler():
    logger.info("Starting live crawler service...")
    logger.info(f"Operating hours: {START_HOUR}:00 - {END_HOUR}:59 EST")
    
    last_entries_crawl_date = None
    
    while True:
        try:
            now = datetime.now(EST)
            current_hour = now.hour
            
            logger.info(f"Current time (EST): {now.strftime('%Y-%m-%d %H:%M:%S')}")

            if START_HOUR <= current_hour <= END_HOUR:
                logger.info("Within operating hours. Checking tasks...")
                
                start_time = time.time()
                try:
                    # 1. Crawl Results (Hourly, only during racing hours)
                    # Typical racing is 12 PM - 11 PM, lets be safe and say 11 AM - 11:59 PM
                    # Since START_HOUR is 0 now, we need an inner check
                    RACING_START_HOUR = 11
                    stats = {}
                    
                    if current_hour >= RACING_START_HOUR:
                         logger.info("Racing hours active. Crawling results...")
                         stats = crawl_historical_races(date.today(), COMMON_TRACKS)
                    else:
                         logger.info("Too early for racing results. Skipping result crawl.")

                    # 2. Crawl Upcoming Entries (Once per day, ANY time)
                    # This ensures data is populated early morning (e.g. 1 AM)
                    today_date = date.today()
                    entry_stats = {'races_found': 0}
                    
                    if last_entries_crawl_date != today_date:
                        logger.info("Entry crawler paused per user request.")
                        # logger.info("First run of the day for Entries. Fetching upcoming races...")
                        # entry_stats = crawl_entries(today_date, COMMON_TRACKS)
                        last_entries_crawl_date = today_date
                    else:
                        logger.info("Entries already crawled today (or paused). Skipping.")

                    duration = time.time() - start_time
                    logger.info(f"Crawl finished in {duration:.1f}s. "
                                f"Results found: {stats.get('races_found', 0)}, "
                                f"Entries found: {entry_stats.get('races_found', 0)}")
                                
                except Exception as e:
                    logger.error(f"Crawl execution failed: {e}")
                
                # Sleep for 1 hour
                logger.info("Sleeping for 1 hour...")
                time.sleep(3600)
            else:
                # Should not happen if START=0, END=23, but kept for safety if config changes
                logger.info("Outside operating hours.")
                time.sleep(3600)

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.info("Retrying in 60 seconds...")
            time.sleep(60)

def signal_handler(sig, frame):
    logger.info("Graceful shutdown received. Exiting.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_crawler()
