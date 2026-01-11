
import sys
import os
import logging
from crawl_equibase import parse_horses_from_text, parse_race_chart_text

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_parsing():
    try:
        with open("debug_text.txt", "r", encoding="utf-8") as f:
            text = f.read()
            
        print("--- Testing Metadata Parsing ---")
        metadata = parse_race_chart_text(text)
        for k, v in metadata.items():
            print(f"{k}: {v}")
            
        print("\n--- Testing Horse Parsing ---")
        horses = parse_horses_from_text(text)
        print(f"Found {len(horses)} horses")
        for h in horses:
            print(h)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_parsing()
