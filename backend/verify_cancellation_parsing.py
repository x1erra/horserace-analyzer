
import logging
from bs4 import BeautifulSoup
from crawl_scratches import fetch_static_page, CANCELLATIONS_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_cancellations():
    rss_url = "https://www.equibase.com/static/latechanges/rss/AQU-USA.rss"
    logger.info(f"Fetching RSS: {rss_url}")
    # Use requests directly first
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(rss_url, headers=headers, timeout=10)
        logger.info(f"RSS Status: {r.status_code}")
        logger.info(f"RSS Content Preview: {r.text[:500]}")
        with open("dump_rss.xml", "w", encoding='utf-8') as f:
            f.write(r.text)
    except Exception as e:
        logger.error(f"RSS Fetch Failed: {e}")

if __name__ == "__main__":
    debug_cancellations()
