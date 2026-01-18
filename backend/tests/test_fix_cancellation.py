
import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import determine_change_type, parse_rss_changes

class TestCancellationParsing(unittest.TestCase):
    def test_determine_change_type_bug(self):
        # This currently returns 'Race Cancelled' which is the bug for wagering
        c_type = determine_change_type("Show Wagering Cancelled")
        print(f"DEBUG: 'Show Wagering Cancelled' -> {c_type}")
        # We WANT this to NOT be 'Race Cancelled'. 
        # But for reproduction, we assert what happens currently or just print it.
        # I will assert strictly what I WANT it to be after fix, so this fails now.
        self.assertNotEqual(c_type, 'Race Cancelled', "Should not be marked as Race Cancelled")

    def test_rss_parsing_wagering(self):
        xml_snippet = """
        <item>
          <description>Race 01: <i>Show Wagering Cancelled</i><br/></description>
        </item>
        """
        changes = parse_rss_changes(xml_snippet, 'AQU')
        print(f"DEBUG RSS changes: {changes}")
        
        for c in changes:
            if c['change_type'] == 'Race Cancelled':
                self.fail("Found 'Race Cancelled' for wagering cancellation")

if __name__ == '__main__':
    unittest.main()
