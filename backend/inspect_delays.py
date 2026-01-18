
import logging
import sys
import os
import re

# Add backend dir to path
sys.path.append(os.path.dirname(__file__))

from crawl_scratches import fetch_rss_feed, parse_rss_changes

logging.basicConfig(level=logging.INFO)

def inspect_feeds():
    tracks = ['AQU', 'HOU']
    
    for code in tracks:
        print(f"\n=== INSPECTING {code} RSS ===")
        xml = fetch_rss_feed(code)
        if not xml: continue
        
        # Parse it using existing parser to see raw descriptions
        changes = parse_rss_changes(xml, code)
        
        print(f"Found {len(changes)} items.")
        for c in changes:
            # Print description if it contains 'Time' or 'Delay' or 'Changed'
            desc = c.get('description', '')
            if any(x in desc.lower() for x in ['time', 'delay', 'mtp', 'post']):
                print(f"  [POTENTIAL DELAY]: {desc}")
            elif 'change' in desc.lower() and 'jockey' not in desc.lower():
                 print(f"  [OTHER CHANGE]: {desc}")

if __name__ == "__main__":
    inspect_feeds()
