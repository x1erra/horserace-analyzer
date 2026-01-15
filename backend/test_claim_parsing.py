
import re
import logging

# Configure logging to see debug output
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def normalize_name(name: str) -> str:
    """Normalize name for more reliable mapping"""
    if not name: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def parse_claims_text(text: str):
    """
    Parse claimed horses information (Improved logic)
    """
    claims = []
    lines = text.split('\n')
    
    # 1. Parse Claiming Prices first to get price map
    price_map = {}
    
    # Flexible regex: Claiming\s*Prices\s*:
    price_match = re.search(r'Claiming\s*Prices\s*:(.*?)(?:Scratched|Total|Footnotes|$)', text, re.DOTALL | re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).strip()
        # Pattern: number - Name: $price
        price_items = re.findall(r'(\d+)\s*-\s*([^:]+):\s*\$([\d,]+)', price_text)
        for num, name, price in price_items:
            # Use improved normalization
            norm_name = normalize_name(name)
            price_val = float(price.replace(',', ''))
            price_map[norm_name] = price_val
            logger.debug(f"Mapped '{name}' (norm: {norm_name}) to {price_val}")

    # 2. Parse Claimed Horse lines
    for line in lines:
        if re.search(r'Claimed\s*Horse\(s\)\s*:', line, re.IGNORECASE):
            try:
                content = re.sub(r'^\d*\s*Claimed\s*Horse\(s\)\s*:\s*', '', line.strip(), flags=re.IGNORECASE)
                parts = re.split(r'\s*New\s*Trainer\s*:\s*|\s*New\s*Owner\s*:\s*', content, flags=re.IGNORECASE)
                
                if len(parts) >= 3:
                    horse_name = parts[0].strip()
                    trainer = parts[1].strip()
                    owner = parts[2].strip()
                    
                    # Use improved normalization for lookup
                    norm_horse_name = normalize_name(horse_name)
                    price = price_map.get(norm_horse_name)
                    
                    if not price:
                        # Fallback to fuzzy/partial matching if still not found
                        for k, v in price_map.items():
                            if k in norm_horse_name or norm_horse_name in k:
                                price = v
                                logger.debug(f"Fuzzy match found: {norm_horse_name} -> {k}")
                                break
                    
                    claims.append({
                        'horse_name': horse_name,
                        'new_trainer': trainer,
                        'new_owner': owner,
                        'claim_price': price
                    })
            except Exception as e:
                logger.debug(f"Error parsing claim line '{line}': {e}")
                continue

    return claims, price_map

# Mocked text from the browser subagent output for TAM 2026-01-14 Race 1
# This is reconstructed to match the concatenated behavior seen in the database
sample_text = """
The winners of the first race are shown below.
Claiming Prices: 8 - Caravaggios Song: $25,000; 7 - New Issue: $25,000; 4 - Go K J Go: $25,000; 2 - Enchant: $25,000; 9 - Growth-Rate: $25,000; 5 - Yammy Yammy Bella: $25,000; 6 - Gambi: $25,000;
Some other text here that might be in the middle.
1 Claimed Horse(s): Growth Rate New Trainer: Kevin Rice New Owner: Rice Racing
"""

if __name__ == "__main__":
    # Test with potential concatenation behavior
    # Note: If the parser normalizes names, we should check how it matches
    claims, prices = parse_claims_text(sample_text)
    print(f"Price Map: {prices}")
    print(f"Extracted Claims: {claims}")
    
    # Check if Growth Rate has a price
    found = False
    for c in claims:
        # Note: Database has 'GrowthRate'
        clean_name = re.sub(r'[^\w\s]', '', c['horse_name']).replace(' ', '')
        if "GrowthRate" in clean_name:
            found = True
            if c['claim_price'] == 25000:
                print(f"SUCCESS: {c['horse_name']} (normalized: {clean_name}) price extracted correctly.")
            else:
                print(f"FAILURE: {c['horse_name']} (normalized: {clean_name}) price is {c['claim_price']}, expected 25000.")
    
    if not found:
        print("FAILURE: Growth Rate claim not found at all.")
