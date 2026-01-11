
import requests
import pdfplumber
import io
import sys

# AQU or any track with a valid PDF but parse issue
url = "https://www.equibase.com/static/chart/pdf/AQU011126USA1.pdf"
print(f"Downloading {url}...")
# Use headers to mimic browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
res = requests.get(url, headers=headers)
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
                with open("debug_text.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                print("Saved text to debug_text.txt")
                
                print("\n--- TABLES STRATEGY TEST ---")
                strategies = [
                    {}, # Default
                    {"vertical_strategy": "text", "horizontal_strategy": "text"},
                    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                    {"vertical_strategy": "explicit", "horizontal_strategy": "text"},
                    {"vertical_strategy": "lines", "horizontal_strategy": "text"},
                ]

                for i, strategy in enumerate(strategies):
                    print(f"Testing Strategy {i}: {strategy}")
                    try:
                        tables = pdf.pages[0].extract_tables(strategy)
                        print(f"  Found {len(tables)} tables")
                        if len(tables) > 0:
                            print(f"  Table 0 row count: {len(tables[0])}")
                            if len(tables[0]) > 0:
                                print(f"  Header: {tables[0][0]}")
                    except Exception as e:
                        print(f"  Strategy failed: {e}")
            else:
                print("PDF has no pages")
else:
    print(f"Failed to download: {res.status_code}")
