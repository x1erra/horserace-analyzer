import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend import app
import json

def run_verification():
    print("Starting Wallet Verification...")
    
    with app.test_client() as client:
        # 1. Check Initial Balance
        print("\n[1] Checking Wallet Balance...")
        res = client.get('/api/wallet')
        if res.status_code != 200:
            print(f"❌ Failed to get wallet: {res.status_code} - {res.data}")
            return
        
        wallet = res.get_json()
        initial_bal = float(wallet['balance'])
        print(f"✅ Current Balance: ${initial_bal:.2f}")
        
        # 2. Add Funds
        print("\n[2] Adding $50.00...")
        res = client.post('/api/wallet/transaction', json={'type': 'deposit', 'amount': 50.00})
        if res.status_code != 200:
             print(f"❌ Failed to add funds: {res.data}")
             return
             
        data = res.get_json()
        new_bal = float(data['balance'])
        print(f"✅ Check: ${new_bal:.2f} (Expected: ${initial_bal + 50:.2f})")
        
        # 3. Find a Race for Betting
        print("\n[3] Finding a valid race for betting...")
        res = client.get('/api/todays-races?status=All')
        races_data = res.get_json()
        races = races_data.get('races', [])
        
        if not races:
            # Try parsing from past races if today is empty?
            res = client.get('/api/past-races?limit=1')
            past_data = res.get_json()
            races = past_data.get('races', [])
            
        if not races:
            print("⚠️ No races found to test betting deduction.")
            return

        target_race = races[0]
        race_id = target_race['id']
        print(f"✅ Found Race: {target_race['track_code']} (ID: {race_id})")
        
        # 4. Place a Bet
        bet_amount = 5.00
        print(f"\n[4] Placing ${bet_amount:.2f} Win Bet...")
        
        bet_payload = {
            'race_id': race_id,
            'bet_type': 'Win',
            'amount': bet_amount,
            'horse_number': '1', 
            'horse_name': 'TestHorse'
        }
        
        res = client.post('/api/bets', json=bet_payload)
        if res.status_code != 200:
            print(f"❌ Failed to place bet: {res.data}")
            return

        bet_res = res.get_json()
        post_bet_bal = float(bet_res['new_balance'])
        print(f"✅ Bet Placed! New Balance: ${post_bet_bal:.2f}")
        
        # Verify Deduction
        expected_bal = new_bal - bet_amount
        if abs(post_bet_bal - expected_bal) < 0.01:
            print(f"✅ Deduction Verified: ${new_bal:.2f} -> ${post_bet_bal:.2f}")
        else:
            print(f"❌ Deduction Mismatch: Expected ${expected_bal:.2f}, Got ${post_bet_bal:.2f}")

        # 5. Clean up (Optional - delete bet)
        # We leave it for now or delete it
        # client.delete(f'/api/bets/{bet_res["bet"]["id"]}')

if __name__ == '__main__':
    run_verification()
