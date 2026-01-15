import logging
import sys
from datetime import date
from crawl_equibase import crawl_historical_races

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TargetedCrawler")

def catchup():
    today = date.today()
    tracks = ['FG', 'SA']
    logger.info(f"Catching up {tracks} for {today}")
    stats = crawl_historical_races(today, tracks)
    logger.info(f"Catchup finished. Stats: {stats}")

if __name__ == "__main__":
    catchup()
