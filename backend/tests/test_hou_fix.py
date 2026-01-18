
import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import parse_rss_changes

class TestHouCancellation(unittest.TestCase):
    def test_superfecta_wagering_cancelled(self):
        xml_snippet = """
        <item>
          <description>Race 02: <i>Superfecta Wagering Cancelled</i><br/></description>
        </item>
        """
        changes = parse_rss_changes(xml_snippet, 'HOU')
        print(f"DEBUG RSS changes: {changes}")
        
        for c in changes:
            if c['change_type'] == 'Race Cancelled':
                self.fail(f"Found 'Race Cancelled' for: {c['description']}")
            elif c['change_type'] == 'Wagering':
                print("SUCCESS: Correctly identified as Wagering change")

if __name__ == "__main__":
    unittest.main()
