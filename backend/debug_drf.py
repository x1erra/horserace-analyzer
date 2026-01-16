
import requests
import logging
from datetime import date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugDRF")


def test_drf():
    url = "https://www.drf.com/results/tracks/SA/country/USA/date/01-14-2026"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    

    try:
        logger.info(f"Fetching {url}...")
        r = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            logger.info("--- BODY SAMPLE (5000-7000) ---")
            logger.info(r.text[5000:7000])
            
            import re
            # Check for Race Headers
            if re.search(r'Race\s+\d+', r.text, re.IGNORECASE):
                logger.info("FOUND 'Race X' header")
            else:
                 logger.info("No 'Race X' header found")
                 
            # Check for generic table markers
            if "payoff" in r.text.lower() or "wager" in r.text.lower():
                logger.info("FOUND Payoff/Wager text")

    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    test_drf()
