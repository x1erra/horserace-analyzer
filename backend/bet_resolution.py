
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def resolve_all_pending_bets(supabase):
    """
    Check pending bets against completed races and resolve them.
    Supports Win, Place, Show, Exacta Box, Trifecta Box, Exotics.
    Returns: Dict with resolution stats
    """
    try:
        # 1. Get all pending bets
        pending_bets = supabase.table('hranalyzer_bets')\
            .select('*, hranalyzer_races(race_status, id)')\
            .eq('status', 'Pending')\
            .execute()
            
        resolved_count = 0
        updated_bets = []
        
        if not pending_bets.data:
            return {
                'success': True,
                'resolved_count': 0,
                'details': []
            }
        
        # Pre-fetch race entries to avoid N+1 queries?
        # For now, keep it simple and query per race since usually few completed races at once.
        # Optimization: Group by race_id
        
        bets_by_race = {}
        for bet in pending_bets.data:
            race = bet.get('hranalyzer_races')
            if not race:
                continue
            
            rid = bet['race_id']
            if rid not in bets_by_race:
                bets_by_race[rid] = []
            bets_by_race[rid].append(bet)
            
        for race_id, bets in bets_by_race.items():
            # Check race status directly from the first bet's race data (optimization)
            # Assuming all bets for race_id have same race data
            race_data = bets[0]['hranalyzer_races']
            is_completed = race_data['race_status'] == 'completed'
            
            # Fetch entries for this race
            entries_resp = supabase.table('hranalyzer_race_entries')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            entries = entries_resp.data
            
            # Fetch exotics for this race
            exotics_resp = supabase.table('hranalyzer_exotic_payouts')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            exotics_data = exotics_resp.data
            
            # Sort winners by position (only if completed, but useful index map anyway)
            finishers = sorted([e for e in entries if e.get('finish_position')], key=lambda x: x['finish_position'])
            
            for bet in bets:
                try:
                    bet_type = bet['bet_type']
                    unit_amount = float(bet['bet_amount'])
                    selection = bet.get('selection')
                    
                    new_status = 'Loss'
                    payout = 0.0
                    
                    # --- RESOLUTION LOGIC ---
                    
                    # Pre-check for Scratches (Applies to ALL race statuses)
                    # For simple bets, we can check the single horse.
                    is_scratched = False
                    
                    if bet_type in ['Win', 'Place', 'Show', 'Win Place', 'Place Show', 'WPS', 'Win Place Show']:
                        horse_number = bet['horse_number']
                        my_horse = next((e for e in entries if str(e['program_number']) == str(horse_number)), None)
                        
                        if my_horse and my_horse.get('scratched'):
                            is_scratched = True
                            
                    # For exotics, if any horse is scratched, it might be a refund or a void depending on rules
                    # Currently simplifying: If any part is scratched -> Refund/Scratched
                    # Real rules might vary (e.g. Box with scratch -> Reduced box)
                    elif selection:
                        # Check if any selected horse is scratched
                        # This is aggressive but safe for now.
                        # Ideally: Exacta Box (1,2,3). 1 Scratched. -> Exacta Box (2,3).
                        # Current Logic: Refund.
                        pass # TODO: Implement complex scratch logic for exotics
                        
                    if is_scratched:
                        new_status = 'Scratched'
                        payout = 0.0 # Refund implies money back, but payout field usually profit?? 
                        # Actually payout usually means "Total Return". Logic below uses payout for update.
                        # Wait, logic says 'payout = 0.0' for Scratched? 
                        # The backend logic for 'Scratched' usually implies the UI handles the refund display or logic handle it.
                        # In the previous code: 'Scratched' set payout = 0.
                        # Let's Stick to that.
                        
                        # UPDATE AND CONTINUE
                        # We resolve this immediately
                        # Refund the cost
                        refund_amount = float(bet.get('bet_cost') or 0.0)
                        if refund_amount == 0:
                            # Fallback if bet_cost missing? Should use unit amount * cost calc? 
                            # Assuming bet_cost is reliably stored.
                            pass

                        update_data = {
                            'status': 'Returned',
                            'payout': refund_amount,
                            'updated_at': datetime.now().isoformat()
                        }
                        supabase.table('hranalyzer_bets').update(update_data).eq('id', bet['id']).execute()
                        resolved_count += 1
                        updated_bets.append({
                            'id': bet['id'], 
                            'old_status': 'Pending', 
                            'new_status': 'Returned',
                            'payout': refund_amount
                        })
                        logger.info(f"Resolved bet {bet['id']} as Returned (Scratch Refund: {refund_amount})")
                        continue


                    # IF NOT SCRATCHED, we only proceed if race is COMPLETED
                    if not is_completed:
                        continue
                    
                    # --- COMPLETED RACE LOGIC BELOW ---
                    
                    if bet_type in ['Win', 'Place', 'Show']:
                        horse_number = bet['horse_number']
                        my_horse = next((e for e in entries if str(e['program_number']) == str(horse_number)), None)
                        
                        if not my_horse:
                            new_status = 'Loss' # Or Void?
                        elif my_horse.get('scratched'):
                            new_status = 'Scratched' # Should have been caught above, but safety check
                        else:
                            pos = my_horse.get('finish_position')
                            if not pos:
                                 new_status = 'Loss'
                            else:
                                if bet_type == 'Win' and pos == 1:
                                    new_status = 'Win'
                                    base_payout = my_horse.get('win_payout') or 0
                                    payout = (float(base_payout) / 2.0) * unit_amount
                                    
                                elif bet_type == 'Place' and pos <= 2:
                                    new_status = 'Win'
                                    base_payout = my_horse.get('place_payout') or 0
                                    payout = (float(base_payout) / 2.0) * unit_amount
                                    
                                elif bet_type == 'Show' and pos <= 3:
                                    new_status = 'Win'
                                    base_payout = my_horse.get('show_payout') or 0
                                    payout = (float(base_payout) / 2.0) * unit_amount

                    elif bet_type == 'Win Place':
                        horse_number = bet['horse_number']
                        my_horse = next((e for e in entries if str(e['program_number']) == str(horse_number)), None)
                        if not my_horse: new_status = 'Loss'
                        elif my_horse.get('scratched'): new_status = 'Scratched'
                        else:
                            pos = my_horse.get('finish_position')
                            if pos:
                                total_payout = 0
                                if pos == 1:
                                    total_payout += (float(my_horse.get('win_payout') or 0) / 2.0) * unit_amount
                                if pos <= 2:
                                    total_payout += (float(my_horse.get('place_payout') or 0) / 2.0) * unit_amount
                                
                                if total_payout > 0:
                                    new_status = 'Win'
                                    payout = total_payout

                    elif bet_type == 'Place Show':
                        horse_number = bet['horse_number']
                        my_horse = next((e for e in entries if str(e['program_number']) == str(horse_number)), None)
                        if not my_horse: new_status = 'Loss'
                        elif my_horse.get('scratched'): new_status = 'Scratched'
                        else:
                            pos = my_horse.get('finish_position')
                            if pos:
                                total_payout = 0
                                if pos <= 2:
                                    total_payout += (float(my_horse.get('place_payout') or 0) / 2.0) * unit_amount
                                if pos <= 3:
                                    total_payout += (float(my_horse.get('show_payout') or 0) / 2.0) * unit_amount
                                
                                if total_payout > 0:
                                    new_status = 'Win'
                                    payout = total_payout

                    elif bet_type == 'WPS' or bet_type == 'Win Place Show':
                        horse_number = bet['horse_number']
                        my_horse = next((e for e in entries if str(e['program_number']) == str(horse_number)), None)
                        
                        if not my_horse:
                            new_status = 'Loss'
                        elif my_horse.get('scratched'):
                            new_status = 'Scratched'
                        else:
                            pos = my_horse.get('finish_position')
                            if not pos:
                                new_status = 'Loss'
                            else:
                                # WPS Logic
                                total_payout = 0.0
                                win_part = 0.0
                                place_part = 0.0
                                show_part = 0.0
                                
                                # Has it won? (1st)
                                if pos == 1:
                                    win_base = my_horse.get('win_payout') or 0
                                    win_part = (float(win_base) / 2.0) * unit_amount
                                    
                                # Has it placed? (1st or 2nd)
                                if pos <= 2:
                                    place_base = my_horse.get('place_payout') or 0
                                    place_part = (float(place_base) / 2.0) * unit_amount
                                    
                                # Has it shown? (1st, 2nd, or 3rd)
                                if pos <= 3:
                                    show_base = my_horse.get('show_payout') or 0
                                    show_part = (float(show_base) / 2.0) * unit_amount
                                    
                                total_payout = win_part + place_part + show_part
                                
                                if total_payout > 0:
                                    new_status = 'Win'
                                    payout = total_payout
                                else:
                                    new_status = 'Loss'

                    elif bet_type in ['Exacta Box', 'Trifecta Box']:
                        if not selection:
                            new_status = 'Loss'
                        else:
                            # Normalize selection list
                            if isinstance(selection, list):
                                norm_selection = [str(x) for x in selection]
                            else:
                                norm_selection = []

                            if len(finishers) < 2:
                                pass # Wait? Or Loss? Assuming Loss for now if race completed
                                
                            else:
                                first_num = str(finishers[0]['program_number'])
                                second_num = str(finishers[1]['program_number'])
                                third_num = str(finishers[2]['program_number']) if len(finishers) >= 3 else None
                                
                                is_win = False
                                wager_label = 'Exacta' if bet_type == 'Exacta Box' else 'Trifecta'
                                
                                if bet_type == 'Exacta Box':
                                    if first_num in norm_selection and second_num in norm_selection:
                                        is_win = True
                                        
                                elif bet_type == 'Trifecta Box':
                                     if third_num and first_num in norm_selection and second_num in norm_selection and third_num in norm_selection:
                                         is_win = True
                                         
                                if is_win:
                                    new_status = 'Win'
                                    # Find Payout
                                    # Filter exotics list in memory
                                    matches = [x for x in exotics_data if wager_label.lower() in x['wager_type'].lower()]
                                    
                                    if matches:
                                        base_payout = matches[0]['payout'] # Simplified: take first match
                                        payout = (float(base_payout) / 2.0) * unit_amount 
                                    else:
                                        payout = 0 
                                        
                    elif ('Key' in bet_type or bet_type in ['Exacta', 'Trifecta']) and selection:
                        # Key/Wheel/Straight Resolution
                        required_positions = 0
                        
                        if 'Exacta' in bet_type: required_positions = 2
                        elif 'Trifecta' in bet_type: required_positions = 3
                        
                        if len(finishers) >= required_positions and len(selection) >= required_positions:
                            is_win = True
                            for i in range(required_positions):
                                finisher_num = str(finishers[i]['program_number'])
                                allowed_for_pos = selection[i] # Expect list of allowed numbers
                                
                                # Normalize allowed
                                norm_allowed = [str(x) for x in allowed_for_pos]
                                
                                if finisher_num not in norm_allowed:
                                    is_win = False
                                    break
                            
                            if is_win:
                                new_status = 'Win'
                                wager_label = 'Exacta' if 'Exacta' in bet_type else 'Trifecta'
                                
                                matches = [x for x in exotics_data if wager_label.lower() in x['wager_type'].lower()]
                                    
                                if matches:
                                    base_payout = matches[0]['payout']
                                    payout = (float(base_payout) / 2.0) * unit_amount
                                else:
                                    payout = 0

                    # Update bet
                    update_data = {
                        'status': new_status,
                        'payout': payout,
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    supabase.table('hranalyzer_bets').update(update_data).eq('id', bet['id']).execute()
                    resolved_count += 1
                    updated_bets.append({
                        'id': bet['id'], 
                        'old_status': 'Pending', 
                        'new_status': new_status,
                        'payout': payout
                    })
                    logger.info(f"Resolved bet {bet['id']} as {new_status} (Payout: {payout})")

                except Exception as e:
                    logger.error(f"Error resolving bet {bet['id']}: {e}")
                    import traceback
                    traceback.print_exc()
            
        return {
            'success': True,
            'resolved_count': resolved_count,
            'details': updated_bets
        }
        
    except Exception as e:
        logger.error(f"Error in resolve_all_pending_bets: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}
