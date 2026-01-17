
import os
import sys
import logging

# Ensure we can import modules from current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawl_scratches import crawl_late_changes
from supabase_client import get_supabase_client

# Setup logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Starting Local Crawler for Remote DB...")
    
    # Authenticate locally
    try:
        sb = get_supabase_client()
        logger.info("✅ Connected to Supabase")
    except Exception as e:
        logger.error(f"❌ Failed to connect to DB: {e}")
        return

    # Run Crawler
    try:
        count = crawl_late_changes()
        logger.info(f"🏁 DONE! Processed {count} changes.")
    except Exception as e:
        logger.error(f"❌ Crawler failed: {e}")

if __name__ == "__main__":
    main()
