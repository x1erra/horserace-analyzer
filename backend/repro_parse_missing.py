import os
import sys
import requests
import pdfplumber
from io import BytesIO
from crawl_equibase import parse_race_chart_text

def download_pdf(pdf_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    try:
        response = requests.get(pdf_url, headers=headers, timeout=30)
        if response.status_code == 200 and response.content.startswith(b'%PDF'):
            return response.content
        else:
            print(f"Failed to download or not a PDF. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Download error: {e}")
        return None

def repro_parse(pdf_url):
    print(f"Downloading {pdf_url}...")
    pdf_bytes = download_pdf(pdf_url)
    
    if not pdf_bytes:
        print("Could not download PDF.")
        return

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = pdf.pages[0].extract_text()
            print("\n--- Extracted Text Start ---")
            print(text)
            print("--- Extracted Text End ---\n")
            
            data = parse_race_chart_text(text)
            print(f"\nParsed Final Time: '{data.get('final_time')}'")
            
            # Debug regex
            import re
            time_match = re.search(r'FINAL\s*TIME:\s*([\d:.]+)', text, re.IGNORECASE)
            print(f"Regex Match: {time_match.group(1) if time_match else 'None'}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with one of the failing URLs from debug output
    url = "https://www.equibase.com/static/chart/pdf/TAM011126USA2.pdf"
    repro_parse(url)
