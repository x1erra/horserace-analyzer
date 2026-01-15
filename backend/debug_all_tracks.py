
import logging
import sys
from datetime import date
from crawl_equibase import crawl_historical_races

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting multi-track verification crawl...")
    
    today = date.today()
    
    # Tracks from user's dashboard + common ones: 
    # Aqueduct (AQU), Fair Grounds (FG), Gulfstream (GP), Parx (PRX), Santa Anita (SA)
    tracks_to_test = ['AQU', 'FG', 'GP', 'PRX', 'SA']
    
    logger.info(f"Target Date: {today}")
    logger.info(f"Tracks to test: {tracks_to_test}")
    
    # Run crawl
    stats = crawl_historical_races(today, tracks_to_test)
    
    logger.info("Multi-track verification finished.")
    logger.info(stats)
