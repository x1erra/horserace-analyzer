
from bs4 import BeautifulSoup
import re
import os

def test_parsing():
    file_path = 'hrn_debug.html'
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    # Simulate the loop in crawl_entries
    for i in range(1, 10):
        race_num = i
        print(f"--- Checking Race {race_num} ---")
        header_div = soup.find(id=f"race-{race_num}")
        if not header_div:
            print("No header found")
            continue

        parent_h2 = header_div.find_parent('h2')
        if parent_h2:
            details_row = parent_h2.find_next_sibling('div', class_='row')
            if details_row:
                # This is the logic we want to implement
                dist_tag = details_row.find(class_='race-distance')
                if dist_tag:
                    raw_text = dist_tag.get_text(strip=True)
                    print(f"Raw Text: '{raw_text}'")
                    

                    # Normalize text: replace newlines with special char, but keep commas in place for now.
                    # We want to split by "logical" separators.
                    # HRN structure: "Distance, Surface, Race Type"
                    # But Race Type can have commas like "$5,000 Claiming" -> split -> "$5", "000 Claiming"
                    
                    # Better approach: Get text with separator, then reconstruct
                    text_content = dist_tag.get_text("|", strip=True) 
                    # "6 f|Dirt|$15,000 Claiming"
                    # or "1 m, 70 y|Dirt|..."
                    
                    # Split by | first
                    raw_parts = [p.strip() for p in text_content.split('|') if p.strip()]
                    
                    # Flatten if potential internal commas (though get_text usually handles separate block elements as separators)
                    # Use a list to accumulate parts
                    final_parts = []
                    for p in raw_parts:
                        # If p contains newlines or excessive whitespace, clean it
                        clean_p = " ".join(p.split())
                        # If it has commas, it complicates things.
                        # Usually HRN puts them in separate lines or spans, which | catches?
                        # Let's see what raw_text was in the debug output.
                        # "1 m,\nDirt,\n$5,000 Claiming" -> get_text("|") -> "1 m,|Dirt,|$5,000 Claiming"
                        # The commas might be text nodes.
                        
                        # Let's try splitting by comma ONLY if it looks like a separator?
                        # Or just trust the order? Distance -> Surface -> Type
                        
                        # Let's split by comma but re-merge currency?
                        sub_parts = [sp.strip() for sp in clean_p.split(',')]
                        for sp in sub_parts:
                            if not sp: continue
                            
                            # Re-merge if previous part ended with digit and this starts with 3 digits? (10,000)
                            if final_parts and re.match(r'^\$\d{1,3}$', final_parts[-1]) and re.match(r'^\d{3}', sp):
                                final_parts[-1] += "," + sp
                            else:
                                final_parts.append(sp)

                    distance = None
                    surface = None
                    race_type_parts = []
                    
                    for part in final_parts:
                        part_lower = part.lower()
                        
                        # Distance Check: starts with digit, contains specific unit
                        # Regex is safer. Handle "5 1/2F" (F attached)
                        # Look for digit followed eventually by unit
                        if not distance and re.match(r'^\d', part) and re.search(r'(m|f|y|mile|furlong|yds)', part_lower):
                             distance = part
                        
                        # Surface Check
                        elif not surface and any(x in part_lower for x in ['dirt', 'turf', 'synthetic', 'all weather']):
                             surface = part
                             
                        # Race Type: Not distance, not surface
                        else:
                             # Exclude pure money if we captured 'purse' elsewhere, but honestly "Claiming $5000" matches race type
                             # We just want to avoid treating "Purse: $14,000" as race type if it leaked in.
                             if 'purse:' in part_lower:
                                 continue
                             race_type_parts.append(part)
                             
                    race_type = " ".join(race_type_parts)
                    print(f"Parsed -> Dist: {distance}, Surf: {surface}, Type: {race_type}")

                    
if __name__ == "__main__":
    test_parsing()
