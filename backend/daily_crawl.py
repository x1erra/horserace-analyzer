#!/usr/bin/env python3
"""
Daily Horse Racing Crawler
Automatically crawls Equibase results for the previous day
Designed to be run daily via cron or Docker scheduler
"""

import os
import sys
import logging
import json
import argparse
from datetime import date, timedelta, datetime
from pathlib import Path
from crawl_equibase import crawl_historical_races, COMMON_TRACKS
from supabase_client import get_supabase_client
from bet_resolution import resolve_all_pending_bets

# Configuration
LOG_DIR = os.getenv('LOG_DIR', '/var/log')
LOG_FILE = os.path.join(LOG_DIR, 'horse-racing-crawler.log')
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB

# Ensure log directory exists (fallback to current dir if /var/log is not writable)
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    # Test write access
    test_file = os.path.join(LOG_DIR, '.test')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
except (PermissionError, OSError):
    # Fall back to backend directory
    LOG_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_FILE = os.path.join(LOG_DIR, 'horse-racing-crawler.log')
    print(f"Warning: Cannot write to /var/log, using {LOG_DIR}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_NO_RACES_FOUND = 1
EXIT_CRAWL_FAILED = 2
EXIT_DATABASE_ERROR = 3
EXIT_CONFIG_ERROR = 4


def log_crawl_to_database(supabase, crawl_date: str, stats: dict, status: str = 'completed'):
    """
    Log crawl run to hranalyzer_crawl_logs table
    """
    try:
        duration = stats.get('duration_seconds', 0)

        log_entry = {
            'crawl_date': crawl_date,
            'crawl_type': 'daily_auto',
            'status': status,
            'tracks_processed': stats.get('tracks_checked', 0),
            'races_updated': stats.get('races_inserted', 0),
            'entries_updated': 0,  # We don't track this separately currently
            'error_message': stats.get('error', None) if status == 'failed' else None,
            'completed_at': datetime.now().isoformat(),
            'duration_seconds': int(duration)
        }

        supabase.table('hranalyzer_crawl_logs').insert(log_entry).execute()
        logger.info(f"Logged crawl run to database")

    except Exception as e:
        logger.error(f"Failed to log crawl to database: {e}")


def check_log_rotation():
    """
    Simple log rotation: if log file exceeds MAX_LOG_SIZE, rotate it
    """
    try:
        if os.path.exists(LOG_FILE):
            size = os.path.getsize(LOG_FILE)
            if size > MAX_LOG_SIZE:
                # Rotate: .log -> .log.1, .log.1 -> .log.2, etc
                for i in range(4, 0, -1):
                    old_file = f"{LOG_FILE}.{i}"
                    new_file = f"{LOG_FILE}.{i+1}"
                    if os.path.exists(old_file):
                        if os.path.exists(new_file):
                            os.remove(new_file)
                        os.rename(old_file, new_file)

                # Move current log to .1
                if os.path.exists(f"{LOG_FILE}.1"):
                    os.remove(f"{LOG_FILE}.1")
                os.rename(LOG_FILE, f"{LOG_FILE}.1")

                logger.info(f"Rotated log file (size was {size} bytes)")
    except Exception as e:
        logger.warning(f"Log rotation failed: {e}")


def main():
    """
    Main entry point for daily crawler
    """
    start_time = datetime.now()

    logger.info("=" * 80)
    logger.info("Daily Horse Racing Crawler Starting")
    logger.info("=" * 80)
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info(f"Log file: {LOG_FILE}")

    # Check log rotation
    check_log_rotation()

    # Parse arguments
    parser = argparse.ArgumentParser(description='Daily Horse Racing Crawler')
    parser.add_validator = lambda x: datetime.strptime(x, '%Y-%m-%d').date()
    parser.add_argument('--date', type=str, help='Target date to crawl (YYYY-MM-DD). Defaults to yesterday.')
    args = parser.parse_args()

    if args.date:
        try:
            # Validate date format
            datetime.strptime(args.date, '%Y-%m-%d')
            crawl_date = args.date
            logger.info(f"Using manual target date: {crawl_date}")
            # Convert to date object for crawler
            target_date_obj = datetime.strptime(crawl_date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
            return EXIT_CONFIG_ERROR
    else:
        # Calculate yesterday's date
        target_date_obj = date.today() - timedelta(days=1)
        crawl_date = target_date_obj.isoformat()
        logger.info(f"Target date: {crawl_date} (defaulting to yesterday)")
    logger.info(f"Tracks to crawl: {', '.join(COMMON_TRACKS)}")

    # Verify environment
    try:
        from dotenv import load_dotenv
        load_dotenv()

        supabase_url = os.getenv('SUPABASE_URL')

        if not supabase_url:
            logger.error("SUPABASE_URL not set in environment")
            return EXIT_CONFIG_ERROR

        logger.info("✓ Environment variables configured")

    except Exception as e:
        logger.error(f"Environment check failed: {e}")
        return EXIT_CONFIG_ERROR

    # Test database connection
    try:
        supabase = get_supabase_client()
        supabase.table('hranalyzer_tracks').select('id').limit(1).execute()
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return EXIT_DATABASE_ERROR

    # Run crawler
    logger.info("")
    logger.info("Starting crawl...")
    logger.info("-" * 80)

    try:
        stats = crawl_historical_races(target_date_obj, COMMON_TRACKS)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        stats['duration_seconds'] = duration

        logger.info("-" * 80)
        logger.info("Crawl completed!")
        logger.info("")
        logger.info("Summary:")
        logger.info(f"  Date: {crawl_date}")
        logger.info(f"  Duration: {duration:.1f} seconds")
        logger.info(f"  Tracks processed: {stats.get('tracks_checked', 0)}")
        logger.info(f"  Races found: {stats.get('races_found', 0)}")
        logger.info(f"  Races inserted: {stats.get('races_inserted', 0)}")

        if stats.get('errors'):
            logger.info(f"  Errors: {len(stats['errors'])}")

        # Log to database
        log_crawl_to_database(supabase, crawl_date, stats, 'completed')
        
        # Resolve Bets
        logger.info("Resolving pending bets...")
        resolve_all_pending_bets(supabase)

        # Determine exit code
        if stats.get('races_found', 0) == 0:
            logger.warning("No races found for this date")
            return EXIT_NO_RACES_FOUND

        if not stats.get('success', False):
            logger.error("Crawl failed")
            return EXIT_CRAWL_FAILED

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"Daily crawler completed successfully")
        logger.info("=" * 80)

        return EXIT_SUCCESS

    except Exception as e:
        logger.error(f"Crawl failed with exception: {e}")
        logger.exception("Full traceback:")

        # Try to log error to database
        try:
            error_stats = {
                'tracks_processed': 0,
                'races_inserted': 0,
                'error': str(e),
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
            log_crawl_to_database(supabase, crawl_date, error_stats, 'failed')
        except:
            pass

        return EXIT_CRAWL_FAILED


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
