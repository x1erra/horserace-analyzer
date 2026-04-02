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
from crawl_scratches import crawl_late_changes
from bet_resolution import resolve_all_pending_bets
from supabase_client import get_supabase_client
from runtime_state import evaluate_runtime_alerts, update_crawl_status

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


def record_crawl_result(crawl_type, success, **details):
    update_crawl_status(crawl_type, success=success, details=details)


def run_entries_refresh(today_date):
    s1 = crawl_entries(today_date, COMMON_TRACKS)
    s2 = crawl_entries(today_date + timedelta(days=1), COMMON_TRACKS)
    s3 = crawl_entries(today_date + timedelta(days=2), COMMON_TRACKS)
    total_found = s1.get('races_found', 0) + s2.get('races_found', 0) + s3.get('races_found', 0)
    record_crawl_result(
        'entries',
        success=True,
        today_races_found=s1.get('races_found', 0),
        tomorrow_races_found=s2.get('races_found', 0),
        day_after_races_found=s3.get('races_found', 0),
        total_races_found=total_found,
    )
    return {'races_found': total_found}


def run_results_refresh(today_date, current_hour):
    stats_today = {}
    stats_yesterday = {}
    if current_hour >= 11 or current_hour < 2:
        logger.info("Racing hours (or late night check) active. Crawling results...")
        stats_today = crawl_historical_races(today_date, COMMON_TRACKS)
        stats_yesterday = crawl_historical_races(today_date - timedelta(days=1), COMMON_TRACKS)
    else:
        logger.info("Slow hours. Performing maintenance check on yesterday's results...")
        stats_yesterday = crawl_historical_races(today_date - timedelta(days=1), COMMON_TRACKS)

    record_crawl_result(
        'results',
        success=True,
        today_races_found=stats_today.get('races_found', 0),
        yesterday_races_found=stats_yesterday.get('races_found', 0),
    )
    return stats_today, stats_yesterday


def run_scratches_refresh():
    logger.info("Checking for Late Scratches...")
    scratches_found = crawl_late_changes()
    logger.info(f"Scratch check complete. Marked: {scratches_found}")
    record_crawl_result('scratches', success=True, changes_processed=scratches_found)
    return scratches_found


def run_startup_backfill(now):
    today_date = now.date()
    logger.info("Running startup self-heal backfill...")
    try:
        run_entries_refresh(today_date)
    except Exception as e:
        logger.error(f"Startup entries refresh failed: {e}")
        record_crawl_result('entries', success=False, error=str(e))

    try:
        run_results_refresh(today_date, now.hour)
    except Exception as e:
        logger.error(f"Startup results refresh failed: {e}")
        record_crawl_result('results', success=False, error=str(e))

    try:
        run_scratches_refresh()
    except Exception as e:
        logger.error(f"Startup scratches refresh failed: {e}")
        record_crawl_result('scratches', success=False, error=str(e))

    evaluate_runtime_alerts(during_racing_hours=8 <= now.hour <= 23)

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
    
    last_entries_crawl_at = None
    run_startup_backfill(datetime.now(EST))
    
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
                    today_date = now.date()
                    # 1. Crawl Results (Hourly, only during racing hours)
                    # Typical racing is 12 PM - 11 PM
                    # We check Today and Yesterday to catch late-night results or missed races from downtime
                    stats_today = {}
                    stats_yesterday = {}
                    
                    # Result crawling is most relevant after 11 AM EST
                    try:
                        stats_today, stats_yesterday = run_results_refresh(today_date, current_hour)
                    except Exception as e:
                        logger.error(f"Results crawl failed: {e}")
                        record_crawl_result('results', success=False, error=str(e))

                    # 2. Crawl Upcoming Entries (Once per day)
                    entry_stats = {'races_found': 0}
                    entry_total_for_alert = None
                    
                    entries_refresh_interval = timedelta(hours=4)
                    should_refresh_entries = (
                        last_entries_crawl_at is None
                        or (now - last_entries_crawl_at) >= entries_refresh_interval
                    )

                    if should_refresh_entries:
                        logger.info("Refreshing entries for Today, Tomorrow, and Day After...")
                        try:
                            entry_stats = run_entries_refresh(today_date)
                            last_entries_crawl_at = now
                            entry_total_for_alert = entry_stats.get('races_found')
                        except Exception as e:
                            logger.error(f"Entries crawl failed: {e}")
                            record_crawl_result('entries', success=False, error=str(e))
                    else:
                        logger.info("Entries refreshed recently. Skipping for now.")

                    duration = time.time() - start_time
                    logger.info(f"Crawl finished in {duration:.1f}s. "
                                f"Results (Y/T): {stats_yesterday.get('races_found', 0)}/{stats_today.get('races_found', 0)}, "
                                f"Entries: {entry_stats.get('races_found', 0)}")
                                
                    # 2.5 Crawl Scratches (Every loop)
                    try:
                        scratches_found = run_scratches_refresh()
                    except Exception as e:
                        logger.error(f"Scratch crawl failed: {e}")
                        record_crawl_result('scratches', success=False, error=str(e))

                    evaluate_runtime_alerts(
                        today_summary_total=entry_total_for_alert,
                        during_racing_hours=8 <= current_hour <= 23,
                    )
                                
                    # 3. Resolve Pending Bets
                    logger.info("Resolving pending bets...")
                    try:
                        supabase = get_supabase_client()
                        resolution_stats = resolve_all_pending_bets(supabase)
                        if resolution_stats.get('resolved_count', 0) > 0:
                            logger.info(f"Resolved {resolution_stats['resolved_count']} bets.")
                    except Exception as e:
                         logger.error(f"Bet resolution failed: {e}")
                                
                except Exception as e:
                    logger.error(f"Crawl execution failed: {e}")
                    # Do not exit, just log and sleep
                
                # Update heartbeat before sleeping
                touch_heartbeat()
                
                # Sleep for 5 minutes (reduced from 15m for better responsiveness)
                logger.info("Sleeping for 5 minutes...")
                time.sleep(300)
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
