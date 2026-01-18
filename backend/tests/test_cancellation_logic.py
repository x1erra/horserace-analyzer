
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import is_valid_cancellation, parse_rss_changes, determine_change_type

class TestCancellationLogic(unittest.TestCase):
    
    def test_is_valid_cancellation(self):
        # Valid Cancellations
        self.assertTrue(is_valid_cancellation("Race Cancelled"))
        self.assertTrue(is_valid_cancellation("Race 1 Cancelled due to weather"))
        self.assertTrue(is_valid_cancellation("Entire card Cancelled"))
        
        # Invalid (Wagering)
        self.assertFalse(is_valid_cancellation("Show Wagering Cancelled"))
        self.assertFalse(is_valid_cancellation("Superfecta Wagering Cancelled"))
        self.assertFalse(is_valid_cancellation("Pick 5 Pool Cancelled"))
        self.assertFalse(is_valid_cancellation("Simulcast Cancelled"))
        
        # Mixed / Tricky
        self.assertFalse(is_valid_cancellation("Turf Racing Cancelled")) # Surface change
        
    def test_rss_wagering_cancellation(self):
        # AQU Case
        xml_aqu = """
        <item>
          <description>Race 01: <i>Show Wagering Cancelled</i><br/></description>
        </item>
        """
        changes = parse_rss_changes(xml_aqu, 'AQU')
        for c in changes:
            self.assertNotEqual(c['change_type'], 'Race Cancelled', "AQU Show Wagering should not cancel race")
            
        # HOU Case
        xml_hou = """
        <item>
          <description>Race 02: <i>Superfecta Wagering Cancelled</i><br/></description>
        </item>
        """
        changes = parse_rss_changes(xml_hou, 'HOU')
        for c in changes:
            self.assertNotEqual(c['change_type'], 'Race Cancelled', "HOU Superfecta Wagering should not cancel race")

    def test_determine_change_type(self):
        self.assertEqual(determine_change_type("Race Cancelled"), "Race Cancelled")
        self.assertNotEqual(determine_change_type("Show Wagering Cancelled"), "Race Cancelled")
        
if __name__ == '__main__':
    unittest.main()
