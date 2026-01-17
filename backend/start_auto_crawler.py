
import os
import sys
import logging
import time
from datetime import datetime

# Ensure we can import modules from current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawl_scratches import crawl_late_changes
from supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LocalAutoCrawler")

def main():
    logger.info("🚀 Starting Local Auto-Crawler Service...")
    logger.info("This script will run continuously and fetch changes every 10 minutes.")
    
    # Authenticate check
    try:
        sb = get_supabase_client()
        logger.info("✅ Connected to Supabase")
    except Exception as e:
        logger.error(f"❌ Failed to connect to DB: {e}")
        return

    while True:
        try:
            logger.info("----------------------------------------")
            logger.info(f"🕒 Starting Crawl at {datetime.now().strftime('%H:%M:%S')}...")
            
            count = crawl_late_changes()
            
            logger.info(f"✅ Crawl finished. Processed {count} changes.")
            
        except KeyboardInterrupt:
            logger.info("🛑 Stopping Auto-Crawler (User Interrupt)")
            break
        except Exception as e:
            logger.error(f"❌ Crawl failed with error: {e}")
            
        logger.info("💤 Sleeping for 10 minutes...")
        # Sleep 10 minutes (600 seconds)
        try:
            time.sleep(600)
        except KeyboardInterrupt:
            logger.info("🛑 Stopping Auto-Crawler during sleep")
            break

if __name__ == "__main__":
    main()
