#!/usr/bin/env python3
"""
Fix GP R13 Jan 24, 2026 — Update with actual Pegasus World Cup results.

VERIFIED RESULTS:
  1st: #5 Skippylongstocking  — Win $45.20, Place $14.20, Show $7.20 (per $2)
  2nd: #11 White Abarrio      — Place $6.60, Show $4.60 (per $2)
  3rd: #3 Full Serrano (ARG)  — Show $6.40 (per $2)
  
  Trifecta 5-11-3: $597.90 per $0.50
  
BETS TO FIX:
  f1dc355f — Win on #5 Skippylongstocking, $20,000
  4b366ecc — Trifecta 5-11-3, $20,000
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))
from datetime import datetime

from supabase_client import get_supabase_client

supabase = get_supabase_client()

RACE_ID = "73b71979-5a0e-4875-9eb2-7c7291aa0c68"

# ========================================
# STEP 1: Update race status to completed
# ========================================
print("STEP 1: Updating race status to 'completed'...")
supabase.table('hranalyzer_races').update({
    'race_status': 'completed',
    'winner_program_number': '5',
    'final_time': '1:48.49'
}).eq('id', RACE_ID).execute()
print("  ✓ Race status set to 'completed'")

# ========================================
# STEP 2: Update finish positions & payouts
# ========================================
print("\nSTEP 2: Updating finish positions and payouts...")

finish_data = {
    '5':  {'finish_position': 1, 'win_payout': 45.20, 'place_payout': 14.20, 'show_payout': 7.20, 'final_odds': 21.0},
    '11': {'finish_position': 2, 'win_payout': None,  'place_payout': 6.60,  'show_payout': 4.60, 'final_odds': None},
    '3':  {'finish_position': 3, 'win_payout': None,  'place_payout': None,  'show_payout': 6.40, 'final_odds': None},
    '9':  {'finish_position': 4, 'win_payout': None,  'place_payout': None,  'show_payout': None, 'final_odds': None},
    '2':  {'finish_position': 5, 'win_payout': None,  'place_payout': None,  'show_payout': None, 'final_odds': None},
}

for pgm, data in finish_data.items():
    res = supabase.table('hranalyzer_race_entries').update(data)\
        .eq('race_id', RACE_ID)\
        .eq('program_number', pgm)\
        .execute()
    name = "(unknown)"
    if res.data:
        name = f"entry updated"
    print(f"  #{pgm}: Position {data['finish_position']} — {name}")

# ========================================
# STEP 3: Add exotic payouts
# ========================================
print("\nSTEP 3: Adding exotic payouts...")

# Trifecta: $597.90 per $0.50 = $1195.80 per $1.00
# For standard payout display: use the per-unit payout
trifecta_payout = {
    'race_id': RACE_ID,
    'wager_type': 'Trifecta',
    'winning_combination': '5-11-3',
    'payout': 597.90  # per $0.50
}

try:
    supabase.table('hranalyzer_exotic_payouts').insert(trifecta_payout).execute()
    print(f"  ✓ Trifecta 5-11-3: $597.90 (per $0.50)")
except Exception as e:
    print(f"  ⚠ Trifecta insert: {e}")

# ========================================
# STEP 4: Fix the bets
# ========================================
print("\nSTEP 4: Fixing bets...")

# Bet 1: Win on #5, $20,000
# Payout: ($45.20 / $2.00) * $20,000 = $452,000
win_bet_id = "f1dc355f-de57-40da-8578-886fdcc8f8ac"
win_payout = (45.20 / 2.0) * 20000.0  # = $452,000

supabase.table('hranalyzer_bets').update({
    'status': 'Win',
    'payout': win_payout,
    'updated_at': datetime.now().isoformat()
}).eq('id', win_bet_id).execute()
print(f"  ✓ Win bet on #5 Skippylongstocking: Loss → Win (Payout: ${win_payout:,.2f})")

# Bet 2: Trifecta 5-11-3, $20,000
# Trifecta pays $597.90 per $0.50
# Per $1.00: $597.90 / 0.50 = $1,195.80
# Payout: $1,195.80 / 2.0 * $20,000 = ... wait
# Actually: Trifecta wager base is $0.50.
# The user bet $20,000 unit amount
# The payout = (payout_per_base / base) * unit_amount  
# = ($597.90 / $0.50) * $20,000 = $23,916,000 <-- that's unrealistic
# Wait, let me reconsider. The bet_resolution code uses: (base_payout / 2.0) * unit_amount
# For exotics it does the same: (float(base_payout) / 2.0) * unit_amount
# The $597.90 is per $0.50 base. If we store it as $597.90 in the exotic_payouts table,
# the resolution code divides by 2 and multiplies by unit_amount.
# That would be: (597.90 / 2.0) * 20000 = $5,979,000 
# That's also quite large. Let me think about what makes sense.
#
# Actually at the racetrack:
# - The trifecta base is $0.50
# - If you bet $20,000 on a $0.50 trifecta, that's 40,000 tickets
# - Each ticket pays $597.90, so total = 40,000 * $597.90 = $23,916,000
#
# But looking at the resolution code: payout = (float(base_payout) / 2.0) * unit_amount
# This formula is designed for $2 base WPS bets where base_payout is "per $2"
# For a $0.50 trifecta, we need: (base_payout / 0.50) * unit_amount
# = (597.90 / 0.50) * 20000 = $23,916,000
#
# But the code divides by 2.0 not 0.50. The stored payout would need to be
# adjusted if we want the formula to work.
#
# To make the formula (base_payout / 2.0) * unit_amount produce the right result:
# We need base_payout = payout_per_dollar * 2.0 = (597.90 / 0.50) * 2.0 = 2391.60
# Then: (2391.60 / 2.0) * 20000 = $23,916,000
#
# Wait no. Let's not overthink this. The simplest and most honest approach:
# The actual payout per dollar bet on the trifecta is $597.90 / $0.50 = $1,195.80 per $1
# User bet $20,000 so total payout = $1,195.80 * $20,000 = $23,916,000
#
# That seems high but Skippylongstocking was 21-1 and the trifecta had a long shot 
# finishing ahead of the favorite. So yeah, that's a massive payout.
#
# Setting payout directly since the formula in resolution code may not handle exotic bases correctly.

trifecta_bet_id = "4b366ecc-ddba-46ac-939c-6551063caf79"
# Per dollar: $597.90 / $0.50 = $1,195.80
# Total: $1,195.80 * $20,000 = $23,916,000
trifecta_total_payout = (597.90 / 0.50) * 20000.0

supabase.table('hranalyzer_bets').update({
    'status': 'Win',
    'payout': trifecta_total_payout,
    'updated_at': datetime.now().isoformat()
}).eq('id', trifecta_bet_id).execute()
print(f"  ✓ Trifecta 5-11-3: Loss → Win (Payout: ${trifecta_total_payout:,.2f})")

# ========================================
# STEP 5: Credit wallet
# ========================================
print("\nSTEP 5: Crediting wallet...")
total_payout = win_payout + trifecta_total_payout

user_ref = 'default_user'
w_res = supabase.table('hranalyzer_wallets').select('*').eq('user_ref', user_ref).single().execute()
wallet = w_res.data
old_balance = float(wallet['balance'])
new_balance = old_balance + total_payout

supabase.table('hranalyzer_wallets').update({'balance': new_balance}).eq('id', wallet['id']).execute()

# Log transactions
supabase.table('hranalyzer_transactions').insert({
    'wallet_id': wallet['id'],
    'amount': win_payout,
    'transaction_type': 'Payout',
    'reference_id': win_bet_id,
    'description': f'Win Payout: Skippylongstocking #5 (Pegasus World Cup)'
}).execute()

supabase.table('hranalyzer_transactions').insert({
    'wallet_id': wallet['id'],
    'amount': trifecta_total_payout,
    'transaction_type': 'Payout',
    'reference_id': trifecta_bet_id,
    'description': f'Trifecta Payout: 5-11-3 (Pegasus World Cup)'
}).execute()

print(f"  Old balance: ${old_balance:,.2f}")
print(f"  Win bet payout: +${win_payout:,.2f}")
print(f"  Trifecta payout: +${trifecta_total_payout:,.2f}")
print(f"  New balance: ${new_balance:,.2f}")

print(f"\n{'='*60}")
print(f"DONE! Both bets resolved as WINS.")
print(f"Total winnings: ${total_payout:,.2f}")
print(f"{'='*60}")
