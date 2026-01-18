
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from crawl_scratches import crawl_late_changes

if __name__ == "__main__":
    print("Forcing Reset & Crawl directly...")
    crawl_late_changes(reset_first=True)
    print("Done.")
