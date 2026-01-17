
import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_hou_results():
    # HOU result URL for today
    # http://www.equibase.com/static/chart/summary/HOU011725USA9.html ? No, summary page
    # https://www.equibase.com/premium/eqbRaceChartCalendar.cfm?TO=N
    # Standard results URL structure? 
    # Actually, let's use the crawler function if possible, or just fetch the summary page
    
    url = "https://www.equibase.com/static/chart/summary/HOU011726USA-EQB.html" 
    # Date format match 2026-01-17 -> 011726
    
    logger.info(f"Fetching {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Status: {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Look for Race 9
            # Text "Race 9"
            r9 = soup.find(string="Race 9")
            if r9:
                logger.info("Found 'Race 9' in summary page!")
                # Get surrounding text or row
                parent = r9.find_parent('tr') or r9.find_parent('div')
                if parent:
                    logger.info(f"Context: {parent.get_text()[:200]}")
            else:
                logger.info("'Race 9' NOT found in summary page.")
                
            # Check RSS for HOU too
            rss_url = "https://www.equibase.com/static/latechanges/rss/HOU-USA.rss"
            r_rss = requests.get(rss_url, headers=headers, timeout=10)
            logger.info(f"RSS Status: {r_rss.status_code}")
            if r_rss.status_code == 200:
                logger.info(f"RSS Preview: {r_rss.text[:500]}")
                if "Race 9" in r_rss.text:
                   logger.info("Race 9 mentioned in RSS!")
                   
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    check_hou_results()
