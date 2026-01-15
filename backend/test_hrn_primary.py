
import logging
from datetime import date
from crawl_entries import crawl_entries

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test Gulfstream for Jan 15
    target_date = date(2026, 1, 15)
    tracks = ['GP']
    stats = crawl_entries(target_date=target_date, tracks=tracks)
    print(f"Test Stats: {stats}")
