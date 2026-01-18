
import logging
import sys
import os

# Add backend dir to path so we can import modules directly
# Add backend dir to path so we can import modules directly
sys.path.append(os.path.dirname(__file__))

from crawl_scratches import fetch_rss_feed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_hou():
    track_code = 'HOU' # Sam Houston
    logger.info(f"Fetching RSS for {track_code}...")
    xml = fetch_rss_feed(track_code)
    
    if xml:
        print("RSS CONTENT:")
        print(xml)
        with open("dump_hou_rss.xml", "w", encoding='utf-8') as f:
            f.write(xml)
    else:
        print("No RSS feed found or fetch failed.")

if __name__ == "__main__":
    debug_hou()
