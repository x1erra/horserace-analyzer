from firecrawl import Firecrawl
import json
import datetime

# Replace with your firecrawl API key
API_KEY = "fc-e0ac820386e840a791942dcc8cb5a6df"

app = Firecrawl(api_key=API_KEY)

# URL for upcoming races
url = "https://www.equibase.com/upcoming.cfm"

# Define schema for structured extraction
schema = {
    "type": "object",
    "properties": {
        "races": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_name": {"type": "string"},
                    "race_number": {"type": "integer"},
                    "date": {"type": "string"},
                    "post_time": {"type": "string"},
                    "surface": {"type": "string"},
                    "distance": {"type": "string"}
                },
                "required": ["track_name", "date"]
            }
        }
    }
}

print(f"Starting structured extraction for {url}...")

# Extract structured data
extract_result = app.extract([url], 
    prompt="Extract the list of upcoming races, including track name, race number, date, post time, surface, and distance.",
    schema=schema
)

# Save to JSON file
today = datetime.date.today().strftime("%Y-%m-%d")
file_name = f"extract-data-{today}.json"
with open(file_name, 'w') as f:
    f.write(extract_result.model_dump_json(indent=2))

print(f"Successfully extracted data to {file_name}")