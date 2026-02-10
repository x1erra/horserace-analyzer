
import os
import sys
import re
from supabase_client import get_supabase_client

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def cleanup_tracks():
    print("Starting Track Name Cleanup...")
    supabase = get_supabase_client()
    
    try:
        # Fetch all tracks
        response = supabase.table('hranalyzer_tracks').select('*').execute()
        tracks = response.data
        
        updates = []
        
        # known mappings for specific issues seen
        specific_fixes = {
            'MAHONINGVALLEYRACECOURSE': 'Mahoning Valley Race Course',
            'TURFPARADISE': 'Turf Paradise',
            'SAMHOUSTONRACEPARK': 'Sam Houston Race Park',
            'WILLROGERSDOWNS': 'Will Rogers Downs',
            'GULFSTREAMPARK': 'Gulfstream Park',
            'TAMPA BAY DOWNS': 'Tampa Bay Downs',
            'OAKLAWNPARK': 'Oaklawn Park',
            'Charles Town': 'Charles Town',
            'Delta Downs': 'Delta Downs',
            'Fair Grounds': 'Fair Grounds',
            'Finger Lakes': 'Finger Lakes',
            'Golden Gate Fields': 'Golden Gate Fields',
            'Hawthorne': 'Hawthorne',
            'Horseshoe Indianapolis': 'Horseshoe Indianapolis',
            'Keeneland': 'Keeneland',
            'Laurel Park': 'Laurel Park',
            'Louisiana Downs': 'Louisiana Downs',
            'Monmouth Park': 'Monmouth Park',
            'Parx Racing': 'Parx Racing',
            'Penn National': 'Penn National',
            'Pimlico': 'Pimlico',
            'Prairie Meadows': 'Prairie Meadows',
            'Presque Isle Downs': 'Presque Isle Downs',
            'Remington Park': 'Remington Park',
            'Ruidoso Downs': 'Ruidoso Downs',
            'Santa Anita Park': 'Santa Anita Park',
            'Saratoga': 'Saratoga',
            'Sunland Park': 'Sunland Park',
            'Turfway Park': 'Turfway Park',
            'Woodbine': 'Woodbine',
            'Zia Park': 'Zia Park',
            'Aqueduct': 'Aqueduct',
            'Belmont Park': 'Belmont Park',
            'Del Mar': 'Del Mar'
        }
        
        for track in tracks:
            original_name = track['track_name']
            track_code = track['track_code']
            track_id = track['id']
            
            new_name = original_name
            changed = False
            
            # check specific bad patterns
            # 1. Contains "Race" followed by digits (e.g. Race1)
            # 2. Contains Date (e.g. February8,2026)
            # 3. Very long name without spaces (e.g. MAHONINGVALLEYRACECOURSE)
            
            # Strategy: 
            # If name looks like a messy filename slug, try to map it to a clean name
            # If no clean mapping found, revert to Track Code as name? Or a title-cased version?
            
            clean_candidate = None
            
            # Check for specific garbage strings first
            # e.g. "MAHONINGVALLEYRACECOURSE-February8,2026-Race1"
            if re.search(r'-\w+\d+,?\d{4}-Race\d+', original_name, re.IGNORECASE):
                # Extract the first part?
                parts = original_name.split('-')
                if parts:
                    base_name = parts[0].upper()
                    # Map base name
                    if base_name in specific_fixes:
                        clean_candidate = specific_fixes[base_name]
                    else:
                        # Fallback: Just use Track Code if we can't determine name?
                        # Or try to readable-ize the base_name
                        clean_candidate = base_name.title()
                changed = True

            # If not caught by specific pattern, check generally
            elif len(original_name) > 40: # Suspiciously long
                 changed = True
                 clean_candidate = track_code # Revert to code if name is garbage

            # Check if name equals code - maybe we can improve it? (Not strictly a fix for "garbage", but good cleanup)
            elif original_name == track_code:
                 # Try to improve? 
                 pass

            if changed and clean_candidate:
                print(f"Fixing Track {track_id} ({track_code}): '{original_name}' -> '{clean_candidate}'")
                
                # Perform Update
                supabase.table('hranalyzer_tracks').update({'track_name': clean_candidate}).eq('id', track_id).execute()
                updates.append({'id': track_id, 'old': original_name, 'new': clean_candidate})
            
            # Also check for duplicate tracks? (Out of scope for this specific task but good to note)
            
        print(f"\nCleanup Complete. {len(updates)} tracks updated.")
        
    except Exception as e:
        print(f"Error executing cleanup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    cleanup_tracks()
