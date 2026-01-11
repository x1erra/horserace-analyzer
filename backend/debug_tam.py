
import requests
import pdfplumber
import io
from crawl_equibase import parse_equibase_pdf, parse_race_chart_text, parse_horse_table

url = "https://www.equibase.com/static/chart/pdf/TAM011126USA1.pdf"
print(f"Downloading {url}...")
res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
print(f"Status: {res.status_code}, Bytes: {len(res.content)}")

if res.status_code == 200:
    # Check if it looks like a PDF
    if not res.content.startswith(b'%PDF'):
        print("\n!!! ERROR: CONTENT IS NOT A PDF !!!")
        print(f"First 500 bytes:\n{res.content[:500]}")
    else:
        with pdfplumber.open(io.BytesIO(res.content)) as pdf:
        if len(pdf.pages) > 0:
            text = pdf.pages[0].extract_text()
            print("\n--- EXTRACTED TEXT ---")
            print(text)
            print("----------------------\n")
            
            print("\n--- TABLES ---")
            tables = pdf.pages[0].extract_tables()
            print(f"Found {len(tables)} tables")
            for i, table in enumerate(tables):
                print(f"Table {i} row count: {len(table)}")
                if len(table) > 0:
                    print(f"Header: {table[0]}")
            
            print("\n--- PARSER RESULT ---")
            files_data = parse_equibase_pdf(res.content)
            print(f"Result keys: {files_data.keys() if files_data else 'None'}")
            if files_data:
                print(f"Horses found: {len(files_data.get('horses', []))}")
