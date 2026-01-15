
import logging
import sys
from datetime import date
from crawl_equibase import crawl_historical_races

# Configure logging to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting manual debug crawl for GP (Gulfstream Park) today...")
    
    today = date.today()
    # today = date(2026, 1, 15) # Verify the date matches the user's date
    
    logger.info(f"Target Date: {today}")
    
    # Run crawl only for GP
    stats = crawl_historical_races(today, ['GP'])
    
    logger.info("Debug crawl finished.")
    logger.info(stats)
