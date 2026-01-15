
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample Text from the specific PDF
SAMPLE_TEXT = """
Winner: ThePrince'sSpur,BayGelding,byCairoPrinceoutofFlyingSpur,byGiant'sCauseway.FoaledFeb13,2019inKentucky.      
Breeder:MikeG.Rutherford
Owner:FlyingPStable    
Trainer:Crichton,Rohan 
3ClaimedHorse(s): Philharmonic NewTrainer:AngelQuiroz NewOwner:KevinOswaldoCruz
ThePrince'sSpur NewTrainer:BeauJ.Chapman NewOw
ner:TenTwentyRacing    
Ticking NewTrainer:JorgeDelgado NewOwner:Heeha
wRacing
ClaimingPrices: 2-ThePrince'sSpur:$12,500;6-LookinAtRoses:$12,500;7-Ticking:$12,500;5-SpeedControl:$12,500;3-      
Philharmonic:$12,500;4-SantostoWilson:$12,500;
"""

def normalize_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def parse_claims_text(text: str):
    claims = []
    lines = text.split('\n')
    
    # 1. Parse Claiming Prices first to get price map
    price_map = {}
    price_match = re.search(r'Claiming\s*Prices\s*:(.*?)(?:Scratched|Total|Footnotes|$)', text, re.DOTALL | re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).strip()
        price_items = re.findall(r'(\d+)\s*-\s*([^:]+):\s*\$\s*([\d,]+)', price_text)
        for num, name, price in price_items:
            norm_name = normalize_name(name)
            price_val = float(price.replace(',', ''))
            price_map[norm_name] = price_val
            print(f"Mapped '{name}' -> {price_val}")
    
    # 2. Parse Claimed Horse lines (NEW LOGIC)
    in_claims_section = False
    current_claim = None
    
    # Regex to identify New Trainer / New Owner labels
    # Note: Text extraction might remove spaces: "NewTrainer:", "NewOwner:"
    label_pattern = re.compile(r'\s*(New\s*Trainer|New\s*Owner)\s*:', re.IGNORECASE)
    
    # Regex to split a claim line: [Horse] [New Trainer:...] [New Owner:...]
    # We look for "New Trainer:" as the divider.
    # We also handle "NewTrainer:" (no space).
    split_pattern = re.compile(r'\s*(?:New\s*Trainer|NewTrainer)\s*:\s*|\s*(?:New\s*Owner|NewOwner)\s*:\s*', re.IGNORECASE)

    for line in lines:
        line_content = line.strip()
        if not line_content:
            continue
            
        # Check start of section
        if re.search(r'Claimed\s*Horse\(s\)\s*:', line, re.IGNORECASE):
            in_claims_section = True
            # Remove the prefix
            line_content = re.sub(r'^\d*\s*Claimed\s*Horse\(s\)\s*:\s*', '', line_content, flags=re.IGNORECASE).strip()
        
        if not in_claims_section:
            continue
            
        # Check end of section
        # Stop at ClaimingPrices, Scratched, etc.
        if re.match(r'(Claiming\s*Prices|Scratched|Total|Fractional|Final|Run-Up)', line_content, re.IGNORECASE):
            in_claims_section = False
            # Save valid last claim if any
            if current_claim:
                claims.append(current_claim)
                current_claim = None
            break
            
        # Detect if this is a new claim line
        # It must have "New Trainer:" (or NewTrainer:)
        if re.search(r'(?:New\s*Trainer|NewTrainer)\s*:', line_content, re.IGNORECASE):
            # Save previous claim if exists
            if current_claim:
                claims.append(current_claim)
                current_claim = None
                
            # Parse new claim line
            # Expected: "HorseName NewTrainer: TrainerName NewOwner: OwnerName"
            # Note: OwnerName might be incomplete/continued on next line
            
            parts = re.split(split_pattern, line_content)
            # parts[0] should be Horse Name
            # parts[1] should be Trainer
            # parts[2] should be Owner (start of)
            
            if len(parts) >= 3:
                horse_name = parts[0].strip()
                trainer = parts[1].strip()
                owner = parts[2].strip()
                
                current_claim = {
                    'horse_name': horse_name,
                    'new_trainer': trainer,
                    'new_owner': owner,
                    'claim_price': None
                }
            else:
                print(f"Warning: Could not split claim line correctly: {line_content}")
                
        else:
            # Continuation line (likely owner name continued)
            if current_claim:
                # Append to owner
                # Check if it looks like a wrapped word or new word?
                # "NewOw" + "ner:TenTwentyRacing" -> This was likely "New Owner:..." split?
                # Wait, if "New Owner" was split, then the previous line WOULD NOT have matched the split_pattern for Owner!
                # Let's look at the example:
                # Line 2: "ThePrince'sSpur NewTrainer:BeauJ.Chapman NewOw"
                # This line has "NewTrainer:", so it matches "New claim line".
                # parts = ["ThePrince'sSpur", "BeauJ.Chapman", "NewOw"] (Wait!)
                # "NewOw" is NOT matched by "New Owner:" regex.
                # So parts will only be len 2? 
                # split_pattern includes "New Owner:"
                pass 
                
    # Handle buffer/state logic again more carefully with the example
    
    return claims

def robust_parse(text):
    print("Parsing Claims...")
    claims = []
    lines = text.split('\n')
    
    price_map = {}
    price_match = re.search(r'Claiming\s*Prices\s*:(.*?)(?:Scratched|Total|Footnotes|$)', text, re.DOTALL | re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).strip()
        price_items = re.findall(r'(\d+)\s*-\s*([^:]+):\s*\$\s*([\d,]+)', price_text)
        for num, name, price in price_items:
            norm_name = normalize_name(name)
            price_val = float(price.replace(',', ''))
            price_map[norm_name] = price_val

    in_claims = False
    current_claim = None
    
    # Patterns
    # Note: (\s*) allows for no space if PDF extraction removed it
    trainer_pat = re.compile(r'\s*(?:New\s*Trainer|NewTrainer)\s*:\s*', re.IGNORECASE)
    owner_pat = re.compile(r'\s*(?:New\s*Owner|NewOwner)\s*:\s*', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Start
        if re.search(r'Claimed\s*Horse\(s\)\s*:', line, re.IGNORECASE):
            in_claims = True
            line = re.sub(r'^\d*\s*Claimed\s*Horse\(s\)\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            
        if not in_claims: continue
        
        # End
        if re.match(r'(Claiming\s*Prices|Scratched|Total|Fractional|Final|Run-Up)', line, re.IGNORECASE):
            if current_claim: claims.append(current_claim)
            in_claims = False
            break
            
        # Logic:
        # Check if line contains "New Trainer"
        trainer_match = trainer_pat.search(line)
        
        if trainer_match:
            # Save previous
            if current_claim: claims.append(current_claim)
            
            # This line starts a claim
            # "HorseName NewTrainer: TrainerName [NewOwner: OwnerName]"
            
            # Split at Trainer
            start_idx = trainer_match.start()
            end_idx = trainer_match.end()
            
            horse_part = line[:start_idx].strip()
            rest = line[end_idx:].strip()
            
            # Now search for Owner in 'rest'
            owner_match = owner_pat.search(rest)
            
            if owner_match:
                # "TrainerName NewOwner: OwnerName"
                o_start = owner_match.start()
                o_end = owner_match.end()
                
                trainer_name = rest[:o_start].strip()
                owner_name = rest[o_end:].strip()
                
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': trainer_name,
                    'new_owner': owner_name
                }
            else:
                # "TrainerName NewOw" (Owner label split)
                # OR "TrainerName" (Owner on next line?)
                # This is tricky. If "New Owner" is split, we won't find it.
                # Example: "ThePrince'sSpur NewTrainer:BeauJ.Chapman NewOw"
                # We have horse_part="ThePrince'sSpur"
                # rest="BeauJ.Chapman NewOw"
                # No owner_match.
                
                # We can assume everything after trainer label is trainer name until we verify otherwise?
                # No, "NewOw" is junk at the end of trainer name.
                
                # Heuristic: Check if line ends with "New" or "NewOw"?
                # Or just treat it as Trainer Name for now, and fix in next line?
                
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': rest, # Provisionally
                    'new_owner': ""
                }
        else:
            # No "New Trainer". Continuation line.
            if current_claim:
                # Append to New Owner?
                # Or fix split labels?
                
                # Example continuation: "ner:TenTwentyRacing"
                # This completes "NewOw" -> "NewOwner:TenTwentyRacing"
                
                # Identify if previous line ended with partial label
                prev_owner = current_claim['new_owner']
                prev_trainer = current_claim['new_trainer']
                
                # Check for "NewOwner" reconstruction
                # previous trainer might end with "NewOw"
                if prev_trainer.endswith("NewOw"):
                     # Combine "NewOw" + line -> "NewOwner:TenTwentyRacing"
                     combined = prev_trainer + line
                     # Now search owner pattern again
                     om = owner_pat.search(combined)
                     if om:
                         # We found it!
                         # Update trainer name (remove NewOw part) and set owner
                         # But wait, we don't know where "NewOw" started in prev_trainer string exactly without assuming.
                         # "BeauJ.Chapman NewOw"
                         
                         # Let's try to match owner_pat in combined string
                         o_start = om.start()
                         o_end = om.end()
                         
                         real_trainer = combined[:o_start].strip()
                         real_owner = combined[o_end:].strip()
                         
                         current_claim['new_trainer'] = real_trainer
                         current_claim['new_owner'] = real_owner
                else:
                    # Just append to owner
                    current_claim['new_owner'] += " " + line
                    current_claim['new_owner'] = current_claim['new_owner'].strip()

    # Final cleanup and pricing
    for c in claims:
        # Match price
        hn = normalize_name(c['horse_name'])
        price = price_map.get(hn)
        if not price:
            # Fuzzy match
            for k, v in price_map.items():
                if k in hn or hn in k:
                    price = v
                    break
        c['claim_price'] = price
        
    return claims

if __name__ == "__main__":
    results = robust_parse(SAMPLE_TEXT)
    import json
    print(json.dumps(results, indent=2))
