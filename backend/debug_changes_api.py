
import os
import sys
from datetime import date
from pprint import pprint

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase_client import get_supabase_client

def debug_changes():
    supabase = get_supabase_client()
    today = date.today().isoformat()
    
    # 1. Fetch from entries
    scratch_query = supabase.table('hranalyzer_race_entries')\
        .select('''
            id, program_number, scratched, updated_at,
            horse:hranalyzer_horses(horse_name),
            race:hranalyzer_races!inner(
                id, track_code, race_date, race_number, post_time
            )
        ''')\
        .eq('scratched', True)\
        .gte('race.race_date', today)
        
    entries_res = scratch_query.execute()
    entries_data = entries_res.data
    
    # 2. Fetch from changes
    changes_query = supabase.table('hranalyzer_changes')\
        .select('''
            id, change_type, description, change_time,
            entry:hranalyzer_race_entries(
                program_number,
                horse:hranalyzer_horses(horse_name)
            ),
            race:hranalyzer_races!inner(
                id, track_code, race_date, race_number
            )
        ''')\
        .gte('race.race_date', today)
        
    changes_res = changes_query.execute()
    changes_data = changes_res.data
    
    # Filter for FG Race 6
    entries_data = [e for e in entries_data if e['race']['track_code'] == 'FG' and e['race']['race_number'] == 6]
    changes_data = [c for c in changes_data if c['race']['track_code'] == 'FG' and c['race']['race_number'] == 6]
    
    print(f"DEBUG: Found {len(entries_data)} entries stats for FG R6")
    print(f"DEBUG: Found {len(changes_data)} changes stats for FG R6")
    
    all_items = []
    
    # Simulate Backend Logic extraction
    for item in entries_data:
        race = item.get('race') or {}
        horse = item.get('horse') or {}
        all_items.append({
            'source': 'entries',
            'track_code': race.get('track_code'),
            'race_date': race.get('race_date'),
            'race_number': race.get('race_number'),
            'horse_name': horse.get('horse_name'),
            'program_number': item.get('program_number'),
            'change_type': 'Scratch',
            'description': 'Scratched',
            'obj': item
        })

    for item in changes_data:
        race = item.get('race') or {}
        entry = item.get('entry') or {}
        horse = entry.get('horse') or {}
        all_items.append({
            'source': 'changes',
            'track_code': race.get('track_code'),
            'race_date': race.get('race_date'),
            'race_number': race.get('race_number'),
            'horse_name': horse.get('horse_name'),
            'program_number': entry.get('program_number'),
            'change_type': item.get('change_type'),
            'description': item.get('description'),
            'obj': item
        })

    print("\n--- KEY GENERATION DEBUG ---")
    grouped = {}
    for item in all_items:
        h_name = item.get('horse_name')
        pgm = item.get('program_number')
        
        r_key = f"{item['track_code']}-{item['race_date']}-{item['race_number']}"
        e_key = None
        if h_name and h_name != "Unknown":
            e_key = h_name
        elif pgm and pgm != "-":
            e_key = f"PGM_{pgm}"
        else:
            e_key = "GENERIC"
            
        full_key = f"{r_key}|{e_key}"
        print(f"Item: {item['source']} | Horse: '{h_name}' | PGM: '{pgm}' | Key: '{full_key}'")
        
        if full_key not in grouped: grouped[full_key] = []
        grouped[full_key].append(item)
        
    print("\n--- SELECTION DEBUG ---")
    final_list = []
    
    # Selection Logic Copy-Paste
    def get_entry_score(e):
        score = 0
        desc = (e.get('description') or "").lower()
        src = e.get('source') # script uses 'source', backend uses '_source'
        ctype = (e.get('change_type') or "").lower()
        
        if src == 'changes': score += 10
        if 'scratch' in ctype: score += 5
        elif 'jockey' in ctype: score += 5
        if "reason unavailable" in desc: score -= 5
        if "scratched" == desc: score -= 5
        score += len(desc) / 100
        return score

    for key, group in grouped.items():
        print(f"Group: {key} (Size: {len(group)})")
        if len(group) == 1:
            final_list.append(group[0])
            print("  -> Auto-kept single item")
        else:
            group.sort(key=lambda x: (
                get_entry_score(x),
                x.get('change_time') or ''
            ), reverse=True)
            
            sub_grouped = {}
            for g in group:
                ctype = g['change_type']
                if 'Scratch' in ctype: ctype = 'Scratch'
                elif 'Jockey' in ctype: ctype = 'Jockey'
                elif 'Weight' in ctype: ctype = 'Weight'
                
                if ctype not in sub_grouped: sub_grouped[ctype] = []
                sub_grouped[ctype].append(g)
            
            for sub_type, candidates in sub_grouped.items():
                print(f"  -> Subtype {sub_type}: {len(candidates)} candidates")
                candidates.sort(key=lambda x: (
                    get_entry_score(x),
                    x.get('change_time') or ''
                ), reverse=True)
                winner = candidates[0]
                final_list.append(winner)
                print(f"     Winner: {winner['description']} (Source: {winner['source']})")
                for loser in candidates[1:]:
                    print(f"     Loser:  {loser['description']} (Source: {loser['source']})")

if __name__ == "__main__":
    debug_changes()


if __name__ == "__main__":
    debug_changes()
