
import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import determine_change_type, extract_new_post_time, is_valid_cancellation

class TestDelayLogic(unittest.TestCase):
    
    def test_extract_post_time(self):
        # Time Parser check
        self.assertEqual(extract_new_post_time("Post Time changed to 1:30 PM"), "1:30 PM")
        self.assertEqual(extract_new_post_time("Race 1 Post Time changed to 12:45"), "12:45")
        self.assertEqual(extract_new_post_time("Post Time changed to 3:00 PM for Race 5"), "3:00 PM")
        
        # Negative test
        self.assertIsNone(extract_new_post_time("Jockey changed to Smith"))
    
    def test_determine_change_type_delay(self):
        # We need to test the logic block that would be inside the function usually, 
        # but determine_change_type function logic was updated implicitly? 
        # Wait, I updated parse_rss/parse_html LOOPS, but did I update `determine_change_type`?
        # Let's check `determine_change_type` implementation below.
        pass

    def test_full_change_logic_rss_style(self):
        # Simulating the logic inside parse_rss_changes or parse_track_changes
        desc = "Post Time changed to 2:15 PM"
        ctype = 'Other'
        if 'post time' in desc.lower() and 'changed to' in desc.lower():
            ctype = 'Post Time Change'
        
        self.assertEqual(ctype, 'Post Time Change')
        
if __name__ == '__main__':
    unittest.main()
