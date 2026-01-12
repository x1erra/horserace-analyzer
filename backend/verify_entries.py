from crawl_entries import crawl_entries
from datetime import date
import logging
import sys

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

print("Starting verification of Equibase Entries Crawler for SA...")
# Target Santa Anita (Western) which might have upcoming races
stats = crawl_entries(date.today(), tracks=['SA'])
print("\n--- Crawler Stats ---")
print(stats)
