
import time
import logging
import re
from selenium.webdriver.common.by import By
from crawl_entries import get_driver

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugPostTime")

def debug_post_time_extraction():
    driver = get_driver()
    try:
        # Direct URL to entries if possible, or go through flow
        # Try a known active track URL pattern if possible, but they change.
        # Best to just hit the entries list and pick one.
        driver.get("https://www.equibase.com/entries")
        time.sleep(5)
        
        # Find a track link
        links = driver.find_elements(By.TAG_NAME, "a")
        target_url = None
        
        # Look for a common track like 'Gulfstream' or 'Aqueduct' or just the first one that looks like a track link
        # The crawler looks for links with text == day number.
        import datetime
        day_str = str(datetime.date.today().day)
        
        logger.info(f"Looking for links with text '{day_str}'")
        
        for link in links:
            try:
                if link.text.strip() == day_str:
                    href = link.get_attribute("href")
                    if "premium" not in href: # Avoid premium links if any
                        logger.info(f"Found candidate: {href}")
                        target_url = href
                        break
            except:
                continue
                
        if not target_url:
            logger.error("No entries link found for today.")
            return

        logger.info(f"Navigating to {target_url}")
        driver.get(target_url)
        time.sleep(3)
        
        # Now dump the HTML around "Post Time"
        page_source = driver.page_source
        
        # Find all occurrences of "Post Time"
        indices = [m.start() for m in re.finditer(r'Post Time', page_source, re.IGNORECASE)]
        
        if not indices:
            logger.error("'Post Time' text not found in page source!")
            # Dump a chunk of the body anyway
            print(page_source[:2000])
        else:
            logger.info(f"Found {len(indices)} occurrences of 'Post Time'")
            for idx in indices[:3]: # Just first 3
                start = max(0, idx - 100)
                end = min(len(page_source), idx + 200)
                snippet = page_source[start:end]
                print(f"\n--- SNIPPET AROUND {idx} ---\n")
                print(snippet)
                print("\n---------------------------\n")
                
                # Test the regex on this snippet
                # Note: The crawler uses BeautifulSoup's get_text(), not raw HTML regex.
                # So we should also try to verify what get_text() produces.
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(snippet, 'html.parser')
                text = soup.get_text()
                print(f"BS4 .get_text(): [{text}]")
                
                # Original Regex
                pt_match = re.search(r'Post Time[:\s]+(\d{1,2}:\d{2}\s*(?:AM|PM)?)', text, re.IGNORECASE)
                if pt_match:
                    print(f"REGEX MATCH: {pt_match.group(1)}")
                else:
                    print("REGEX FAIL")
                    
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_post_time_extraction()
