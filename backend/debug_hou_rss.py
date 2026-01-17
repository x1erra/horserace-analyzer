
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_hou_rss_full():
    url = "https://www.equibase.com/static/latechanges/rss/HOU-USA.rss"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            logger.info("RSS Content:")
            print(r.text)
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    check_hou_rss_full()
