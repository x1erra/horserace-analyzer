import os
import sys
from datetime import date
import re
from io import BytesIO
import pdfplumber
import requests

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from crawl_equibase import download_pdf, parse_race_chart_text

def test_text_inspection():
    url = "https://www.equibase.com/static/chart/pdf/FG010426USA1.pdf"
    print(f"Downloading: {url}")
    
    pdf_bytes = download_pdf(url)
    if not pdf_bytes:
        print("Download failed")
        return

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text()
        print("--- EXTRACTED TEXT START ---")
        print(text[:1000]) # First 1000 chars
        print("--- EXTRACTED TEXT END ---")
        
        # Test the ACTUAL function from crawl_equibase
        data = parse_race_chart_text(text)
        print(f"Function Result - Final Time: {data.get('final_time')}")
        
        # Manually verify regex if function fails
        time_match = re.search(r'FINAL\s*TIME:\s*([\d:.]+)', text, re.IGNORECASE)
        if time_match:
             print(f"Manual Regex Match (new): {time_match.group(1)}")
        else:
             print("Manual Regex Match (new): FAILED")

if __name__ == "__main__":
    test_text_inspection()
