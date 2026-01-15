
import logging
import time
from datetime import date, timedelta
from crawl_entries import crawl_entries, COMMON_TRACKS

logger = logging.getLogger(__name__)

def run_backfill(days_back=7, days_forward=2):
    """
    Backfill race entries for a range of dates
    """
    today = date.today()
    start_date = today - timedelta(days=days_back)
    end_date = today + timedelta(days=days_forward)
    
    current_date = start_date
    while current_date <= end_date:
        logger.info(f"\n{'='*40}")
        logger.info(f"BACKFILLING DATE: {current_date}")
        logger.info(f"{'='*40}")
        
        try:
            # We use crawl_entries which now prioritizes HRN
            # We allow completed updates here to fill in missing metadata/jockeys
            stats = crawl_entries(target_date=current_date, tracks=COMMON_TRACKS, allow_completed_update=True)
            logger.info(f"Stats for {current_date}: {stats}")
        except Exception as e:
            logger.error(f"Error backfilling {current_date}: {e}")
            
        current_date += timedelta(days=1)
        time.sleep(5) # Be gentle during backfill

if __name__ == "__main__":
    import argparse
    import os
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description='Backfill race entries.')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--days-back', type=int, default=5, help='Days before today to start')
    parser.add_argument('--days-forward', type=int, default=2, help='Days after today to end')
    
    args = parser.parse_args()
    
    backend_dir = os.path.dirname(__file__)
    log_file = os.path.join(backend_dir, 'crawler.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    
    if args.start_date:
        start_dt = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        today = date.today()
        # If user provides start_date, we just run from there to today + days_forward
        end_dt = today + timedelta(days=args.days_forward)
        
        current_date = start_dt
        while current_date <= end_dt:
            logger.info(f"\n{'='*40}")
            logger.info(f"BACKFILLING DATE: {current_date}")
            logger.info(f"{'='*40}")
            stats = crawl_entries(target_date=current_date, tracks=COMMON_TRACKS, allow_completed_update=True)
            logger.info(f"Stats for {current_date}: {stats}")
            current_date += timedelta(days=1)
            time.sleep(5)
    else:
        # Default behavior: relative to today
        run_backfill(days_back=args.days_back, days_forward=args.days_forward)
