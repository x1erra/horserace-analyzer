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
START_HOUR = 12
END_HOUR = 23 # Run up to and including 11 PM hour

def run_crawler():
    logger.info("Starting live crawler service...")
    logger.info(f"Operating hours: {START_HOUR}:00 - {END_HOUR}:59 EST")
    
    while True:
        try:
            now = datetime.now(EST)
            current_hour = now.hour
            
            logger.info(f"Current time (EST): {now.strftime('%Y-%m-%d %H:%M:%S')}")

            if START_HOUR <= current_hour <= END_HOUR:
                logger.info("Within operating hours. Initiating crawl...")
                
                start_time = time.time()
                try:
                    # Crawl today's races
                    stats = crawl_historical_races(date.today(), COMMON_TRACKS)
                    
                    # Also crawl upcoming entries for today
                    entry_stats = crawl_entries(date.today(), COMMON_TRACKS)
                    
                    duration = time.time() - start_time
                    logger.info(f"Crawl finished in {duration:.1f}s. "
                                f"Results found: {stats.get('races_found', 0)}, "
                                f"Entries found: {entry_stats.get('races_found', 0)}")
                                
                except Exception as e:
                    logger.error(f"Crawl execution failed: {e}")
                    # Don't crash the loop, just log and wait
                
                # Sleep for 1 hour
                logger.info("Sleeping for 1 hour...")
                time.sleep(3600)
                
            else:
                logger.info("Outside operating hours.")
                
                # Calculate time until next start time
                next_start = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
                
                if current_hour > END_HOUR:
                    # It's late (e.g. midnight or 1AM), schedule for later today (if today is new day) 
                    # OR if we are past end hour (e.g. 23), next start is tomorrow.
                    # Actually, if Hour is 0, 1... 11, we are before START_HOUR.
                    # If Hour is 23, we are in operating hours (handled above).
                    # So this logic covers hours < 12 and > 23 (if any, e.g. 24? no).
                    next_start += timedelta(days=1)
                elif current_hour < START_HOUR:
                    # It's morning, next start is today
                    pass
                
                # Double check we are in future
                if next_start <= now:
                    next_start += timedelta(days=1)
                    
                sleep_seconds = (next_start - now).total_seconds()
                hours_sleep = sleep_seconds / 3600
                logger.info(f"Sleeping until {next_start.strftime('%Y-%m-%d %H:%M:%S')} ({hours_sleep:.1f} hours)")
                
                # Sleep in smaller chunks to be responsive to interrupts? 
                # For now simple sleep
                time.sleep(sleep_seconds)

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
