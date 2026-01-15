import time
import logging
import signal
import sys
import os
import tempfile
import pytz
from datetime import datetime, date, timedelta
from crawl_equibase import crawl_historical_races, COMMON_TRACKS
from crawl_entries import crawl_entries

# Configure logging
log_dir = os.getenv('LOG_DIR', '.')
log_file = os.path.join(log_dir, 'live_crawler.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("LiveCrawler")

# Constants
EST = pytz.timezone("America/New_York")
START_HOUR = 0
END_HOUR = 23 # Run 24/7 to ensure morning races are captured
HEARTBEAT_FILE = os.path.join(tempfile.gettempdir(), "crawler_heartbeat")

def touch_heartbeat():
    """Update heartbeat file to signal health to Docker"""
    try:
        with open(HEARTBEAT_FILE, 'w') as f:
            f.write(str(time.time()))
        logger.debug(f"Heartbeat updated at {HEARTBEAT_FILE}")
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")

def run_crawler():
    logger.info("Starting live crawler service...")
    logger.info(f"Operating hours: {START_HOUR}:00 - {END_HOUR}:59 EST")
    
    # Touch heartbeat immediately on startup
    touch_heartbeat()
    
    last_entries_crawl_date = None
    
    while True:
        try:
            now = datetime.now(EST)
            current_hour = now.hour
            
            logger.info(f"Current time (EST): {now.strftime('%Y-%m-%d %H:%M:%S')}")

            # Always touch heartbeat at start of loop
            touch_heartbeat()

            if START_HOUR <= current_hour <= END_HOUR:
                logger.info("Within operating hours. Checking tasks...")
                
                start_time = time.time()
                try:
                    # 1. Crawl Results (Hourly, only during racing hours)
                    # Typical racing is 12 PM - 11 PM
                    # We check Today and Yesterday to catch late-night results or missed races from downtime
                    stats_today = {}
                    stats_yesterday = {}
                    
                    # Result crawling is most relevant after 11 AM EST
                    if current_hour >= 11 or current_hour < 2: # 11 AM to 2 AM next day
                         logger.info("Racing hours (or late night check) active. Crawling results...")
                         stats_today = crawl_historical_races(today_date, COMMON_TRACKS)
                         stats_yesterday = crawl_historical_races(today_date - timedelta(days=1), COMMON_TRACKS)
                    else:
                         logger.info("Slow hours. Performing maintenance check on yesterday's results...")
                         stats_yesterday = crawl_historical_races(today_date - timedelta(days=1), COMMON_TRACKS)

                    # 2. Crawl Upcoming Entries (Once per day)
                    entry_stats = {'races_found': 0}
                    
                    if last_entries_crawl_date != today_date:
                        logger.info("First run of the day for Entries. Fetching upcoming races for Today, Tomorrow, and Day After...")
                        
                        # Crawl today (in case of changes)
                        s1 = crawl_entries(today_date, COMMON_TRACKS)
                        # Crawl tomorrow (primary advance data)
                        s2 = crawl_entries(today_date + timedelta(days=1), COMMON_TRACKS)
                        # Crawl day after (bonus advance data)
                        s3 = crawl_entries(today_date + timedelta(days=2), COMMON_TRACKS)
                        
                        entry_stats['races_found'] = s1.get('races_found', 0) + s2.get('races_found', 0) + s3.get('races_found', 0)
                        last_entries_crawl_date = today_date
                    else:
                        logger.info("Entries already crawled today. Skipping.")

                    duration = time.time() - start_time
                    logger.info(f"Crawl finished in {duration:.1f}s. "
                                f"Results (Y/T): {stats_yesterday.get('races_found', 0)}/{stats_today.get('races_found', 0)}, "
                                f"Entries: {entry_stats.get('races_found', 0)}")
                                
                except Exception as e:
                    logger.error(f"Crawl execution failed: {e}")
                    # Do not exit, just log and sleep
                
                # Update heartbeat before sleeping
                touch_heartbeat()
                
                # Sleep for 15 minutes
                logger.info("Sleeping for 15 minutes...")
                time.sleep(900)
            else:
                # Outside operating hours
                logger.info("Outside operating hours (00:00 - 23:59). Sleeping 1 hour.")
                touch_heartbeat()
                time.sleep(3600)

        except Exception as e:
            logger.error(f"CRITICAL: Unexpected error in main loop: {e}")
            logger.info("Retrying in 60 seconds...")
            # Sleep to prevent rapid restarts if error is persistent
            time.sleep(60)

def signal_handler(sig, frame):
    logger.info("Graceful shutdown received. Exiting.")
    try:
        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)
    except:
        pass
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_crawler()
