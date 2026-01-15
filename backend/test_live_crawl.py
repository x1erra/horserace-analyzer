import logging
import sys
from datetime import date
from crawl_equibase import crawl_historical_races, COMMON_TRACKS

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TestCrawler")

def test_crawl():
    today = date.today()
    logger.info(f"Starting test crawl for {today}")
    # Only check a few tracks mentioned by user to save time
    test_tracks = ['AQU', 'FG', 'SA', 'GP', 'PRX']
    stats = crawl_historical_races(today, test_tracks)
    logger.info(f"Test crawl finished. Stats: {stats}")

if __name__ == "__main__":
    test_crawl()
