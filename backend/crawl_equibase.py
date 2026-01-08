import datetime
import json
import os
import sys
from firecrawl import FirecrawlApp

def crawl_and_parse(pdf_url=None, output_file=None):
    # Hardcoded API key for testing
    api_key = 'fc-e0ac820386e840a791942dcc8cb5a6df'
    app = FirecrawlApp(api_key=api_key)

    if not pdf_url:
        # Default test URL
        pdf_url = "https://www.equibase.com/static/chart/pdf/GP010424USA.pdf"
    
    print(f"Starting structured extraction for {pdf_url}...")

    schema = {
        "type": "object",
        "properties": {
            "track_name": {"type": "string"},
            "date": {"type": "string"},
            "races": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "race_number": {"type": "integer"},
                        "post_time": {"type": "string"},
                        "surface": {"type": "string"},
                        "distance": {"type": "string"},
                        "race_type": {"type": "string"},
                        "conditions": {"type": "string"},
                        "purse": {"type": "string"},
                        "horses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "program_number": {"type": "string"},
                                    "horse_name": {"type": "string"},
                                    "jockey": {"type": "string"},
                                    "trainer": {"type": "string"},
                                    "owner": {"type": "string"},
                                    "weight": {"type": "integer"},
                                    "odds": {"type": "string"},
                                    "finish_position": {"type": "integer"},
                                    "comments": {"type": "string"},
                                    "pace_figures": {"type": "array", "items": {"type": "string"}},
                                    "speed_figure": {"type": "integer"}
                                },
                                "required": ["program_number", "horse_name", "jockey", "trainer"]
                            }
                        },
                        "fractional_times": {"type": "array", "items": {"type": "string"}},
                        "final_time": {"type": "string"}
                    },
                    "required": ["race_number", "horses"]
                }
            }
        },
        "required": ["track_name", "date", "races"]
    }

    try:
        extract_result = app.extract(
            urls=[pdf_url], # Firecrawl expects 'urls' list
            prompt="Extract the full list of all races from this Equibase chart PDF. Include all horses, jockeys, trainers, positions, and odds.",
            schema=schema
        )

        if not output_file:
            today = datetime.date.today().strftime("%Y-%m-%d")
            output_file = f"extract-data-{today}.json"

        # Ensure directory exists if saving to subfolder
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)

        # Handle Pydantic models/objects from Firecrawl SDK
        if hasattr(extract_result, 'model_dump'):
            final_data = extract_result.model_dump()
        elif hasattr(extract_result, 'dict'):
            final_data = extract_result.dict()
        elif hasattr(extract_result, 'data'):
            final_data = {"data": extract_result.data}
        else:
            final_data = extract_result

        with open(output_file, 'w') as f:
            json.dump(final_data, f, indent=2, default=str)

        print(f"Successfully extracted data to {output_file}")
        return True
    except Exception as e:
        print(f"Extraction failed: {str(e)}")
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    crawl_and_parse(url, out)