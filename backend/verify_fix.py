
import sys
import os
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'horserace-analyzer', 'backend'))

# Import the modified function
from crawl_equibase import parse_claims_text

# Same sample text as before (from the PDF) to verify regression/correctness
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

if __name__ == "__main__":
    print("Testing parse_claims_text from crawl_equibase.py...")
    claims = parse_claims_text(SAMPLE_TEXT)
    print(json.dumps(claims, indent=2))
    
    # Assertions
    assert len(claims) == 3, f"Expected 3 claims, got {len(claims)}"
    
    # Check claim 1
    c1 = next(c for c in claims if c['horse_name'] == 'Philharmonic')
    assert c1['claim_price'] == 12500.0
    assert c1['new_trainer'] == 'AngelQuiroz'
    assert c1['new_owner'] == 'KevinOswaldoCruz'
    
    # Check claim 2 (split owner)
    c2 = next(c for c in claims if "ThePrince" in c['horse_name'])
    assert c2['claim_price'] == 12500.0
    assert c2['new_trainer'] == 'BeauJ.Chapman'
    assert 'TenTwenty' in c2['new_owner']
    
    print("\nVERIFICATION PASSED: All claims parsed correctly.")
