
import logging
import sys
import os

# Add backend dir to path so we can import modules directly
sys.path.append(os.path.dirname(__file__))

from crawl_scratches import fetch_rss_feed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_delays():
    # Common tracks for today
    tracks = ['AQU', 'HOU', 'GP', 'SA', 'TAM', 'OP', 'FG'] 
    
    print("Checking for delays...")
    found_any = False
    
    for code in tracks:
        print(f"--- Checking {code} ---")
        xml = fetch_rss_feed(code)
        if not xml:
            print("  No feed.")
            continue
            
        xml_lower = xml.lower()
        
        # Keywords to look for
        keywords = ['delay', 'post time changes', 'post time changed', 'changed to']
        
        found_in_track = False
        for k in keywords:
            if k in xml_lower:
                found_in_track = True
                found_any = True
                print(f"  [!] Found keyword '{k}' in {code} feed!")
                
        if found_in_track:
            # Dump snippet
            # Naive snippet extraction
            start = xml_lower.find('post time')
            if start != -1:
                print(f"  Snippet: ... {xml[start:start+100]} ...")
            else:
                 start = xml_lower.find('delay')
                 if start != -1:
                    print(f"  Snippet: ... {xml[start:start+100]} ...")

    if not found_any:
        print("\nNo obvious delay keywords found in these tracks.")

if __name__ == "__main__":
    check_delays()
