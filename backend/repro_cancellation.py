
import sys
import os
import re
import logging

# Mock logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Copy-paste is_valid_cancellation from crawl_scratches.py
def is_valid_cancellation(text):
    """
    Centralized validation for race cancellations.
    Returns True if this is a legitimate race cancellation, False if it's wagering or other noise.
    """
    if not text: return False
    text_lower = text.lower()
    
    if 'cancel' not in text_lower:
        return False
        
    # EXCLUSION LIST
    # 'wagering' -> "Show Wagering Cancelled"
    # 'simulcast' -> "Simulcast Cancelled" (usually barely matters, but let's be safe)
    # 'turf' -> "Turf Racing Cancelled" (Usually means surface change, not race cancel)
    # 'superfecta', 'trifecta', etc are covered by 'wagering' usually, but 'Show Wagering' is the key one.
    
    # 'superfecta', 'trifecta', 'exacta', 'daily double', 'pick' are also wagering terms.
    
    exclusion_keywords = ['wagering', 'simulcast', 'pool', 'turf racing', 'superfecta', 'trifecta', 'exacta', 'daily double', 'pick']
    
    if any(k in text_lower for k in exclusion_keywords):
        return False
        
    return True

# Test cases
test_cases = [
    "Race Cancelled",
    "Superfecta Wagering Cancelled",
    "Show Wagering Cancelled",
    "Simulcast Cancelled",
    "Turf Racing Cancelled",
    "Results Cancelled", # ?
    "Race 2 Cancelled",
    "Cancelled",
    "Exacta Cancelled",
    "Race 02: Superfecta Wagering Cancelled",
    "Race 02: <i>Superfecta Wagering Cancelled</i>" 
]

print("--- Testing is_valid_cancellation ---")
for t in test_cases:
    res = is_valid_cancellation(t)
    print(f"'{t}' -> {res}")


# Mock parse_rss_changes logic to see what happens with the specific RSS item
from bs4 import BeautifulSoup
def normalize_pgm(p): return p
def normalize_name(n): return n

def parse_rss_changes_mock(xml_content):
    soup = BeautifulSoup(xml_content, 'html.parser')
    items = soup.find_all('item')
    changes = []
    
    for item in items:
        desc = item.description.text if item.description else ""
        lines = re.split(r'<br\s*/?>', desc)
        
        for line in lines:
            if not line.strip(): continue
            print(f"Processing Line: '{line}'")
            
            # Logic from crawl_scratches.py
            m_cancel = re.search(r'Race\s*(\d+):.*?Race Cancelled.*?- (.*)', line, re.IGNORECASE | re.DOTALL)
            if m_cancel:
                desc = m_cancel.group(2).strip()
                if is_valid_cancellation(line) or is_valid_cancellation(desc):
                   print(f"  -> MATCHED Race Cancelled Regex. Validated True.")
                else:
                    print(f"  -> MATCHED Race Cancelled Regex. Validated FALSE. Type=Wagering/Other")
                continue
                
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            print(f"  -> Clean: '{clean_line}'")
            
            m_race = re.match(r'Race\s*(\d+):', clean_line)
            if not m_race: 
                print("  -> No Race Match")
                continue
            r_num = int(m_race.group(1))
            
            content = clean_line[m_race.end():].strip()
            # remainder logic
            m_horse = re.match(r'#\s*(\w+)\s+(.*?)\s+(Scratched|Scratch Reason|Jockey|Weight|First Start|Gelding|Correction|Equipment|Workouts)', content, re.IGNORECASE)
            
            remainder = content
            if m_horse:
                remainder = content[m_horse.end() - len(m_horse.group(3)):]
            
            print(f"  -> Remainder: '{remainder}'")
            
            if 'scratched' in remainder.lower():
                print("  -> Type: Scratch")
            elif is_valid_cancellation(remainder):
                print("  -> Type: RACE CANCELLED (via remainder)")
            elif 'cancel' in remainder.lower():
                print("  -> Type: Wagering/Other (via remainder)")
            else:
                print("  -> Type: Other")

print("\n--- Testing RSS Parsing ---")
rss_xml = """<item>
      <title>Equibase HOU Changes &amp; Scratches 01/18/2026 12:17:45 PM</title>
      <link>http://www.equibase.com/static/latechanges/html/latechangesHOU-USA.html</link>
      <description>Race 02: &lt;i&gt;Superfecta Wagering Cancelled&lt;/i&gt;&lt;br/&gt;</description>
    </item>"""
parse_rss_changes_mock(rss_xml)
