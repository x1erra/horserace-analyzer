import logging
import sys
import os
from bs4 import BeautifulSoup

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawl_scratches import parse_late_changes_index, fetch_static_page, parse_track_changes, LATE_CHANGES_INDEX_URL

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug_output_py.txt", mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TestChangesCrawler")

def test_crawl():
    logger.info("Starting test crawl for Changes...")
    
    logger.info(f"Fetching Index: {LATE_CHANGES_INDEX_URL}")
    html = fetch_static_page(LATE_CHANGES_INDEX_URL)
    
    if not html:
        logger.error("Failed to fetch Index HTML.")
        return
        
    logger.info(f"Fetched HTML Size: {len(html)}")
    logger.info(f"Snippet: {html[:500]}")
    
    soup = BeautifulSoup(html, 'html.parser')
    all_links = [a['href'] for a in soup.find_all('a', href=True)]
    logger.info(f"Total links on page: {len(all_links)}")
    
    # Print first 10 links to see what they look like
    for i, link in enumerate(all_links[:10]):
        logger.info(f"Link {i}: {link}")
        
    links = parse_late_changes_index()
    logger.info(f"Parsed Track Links: {len(links)}")
    
    if not links:
        logger.error("No track links parsed.")
        return

    # Pick a popular track likely to have changes (GP, SA, AQU, OP)
    target = next((x for x in links if x['track_code'] in ['GP', 'SA', 'AQU', 'OP', 'FG']), links[0])
    
    logger.info(f"Testing Track: {target['track_code']} URL: {target['url']}")
    
    html = fetch_static_page(target['url'])
    if not html:
        logger.error("Failed to fetch HTML")
        return
        
    changes = parse_track_changes(html, target['track_code'])
    logger.info(f"Found {len(changes)} changes:")
    for c in changes:
        logger.info(c)

if __name__ == "__main__":
    test_crawl()
