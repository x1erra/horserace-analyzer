
import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_equibase import parse_wps_payouts

class TestWPSParsing(unittest.TestCase):
    def test_parse_standard_payouts(self):
        # Text based on the user's screenshot
        text = """
        Sunland Park - January 3, 2026 - Race 8
        ...
        Total WPS Pool: $22,481
        Pgm Horse Win Place Show Wager Type Winning Numbers Payoff Pool
        3 Daylan 15.60 8.00 5.00 $1.00 Exacta 3-4 125.80 17,024
        4 One Signature Trick 33.60 11.00 $1.00 Trifecta 3-4-6 898.90 10,462
        6 Holland Flash 4.20 $0.10 Superfecta 3-4-6-1 213.58 8,803
        
        Past Performance Running Line Preview
        """
        
        payouts = parse_wps_payouts(text)
        
        # Verify Number 3 (Winner)
        self.assertIn('3', payouts)
        self.assertEqual(payouts['3']['win'], 15.60)
        self.assertEqual(payouts['3']['place'], 8.00)
        self.assertEqual(payouts['3']['show'], 5.00)
        
        # Verify Number 4 (Place)
        self.assertIn('4', payouts)
        self.assertIsNone(payouts['4']['win'])
        self.assertEqual(payouts['4']['place'], 33.60)
        self.assertEqual(payouts['4']['show'], 11.00)
        
        # Verify Number 6 (Show)
        self.assertIn('6', payouts)
        self.assertIsNone(payouts['6']['win'])
        self.assertIsNone(payouts['6']['place'])
        self.assertEqual(payouts['6']['show'], 4.20)

    def test_parse_complex_names(self):
        text = """
        Total WPS Pool: $10,000
        Pgm Horse Win Place Show
        1A My Horse name 4.20 3.00 2.20
        2 Horse Two 5.60 3.40
        3 Matches 2.10
        """
        payouts = parse_wps_payouts(text)
        
        self.assertEqual(payouts['1A']['win'], 4.20)
        self.assertEqual(payouts['2']['place'], 5.60) # Wait, logic check: usually 2nd row is Place/Show
        # Actually in common layout:
        # 1st line: W P S
        # 2nd line: P S
        # 3rd line: S
        # So for '2 Horse Two 5.60 3.40', 5.60 is Place, 3.40 is Show.
        
        self.assertEqual(payouts['2']['place'], 5.60)
        self.assertEqual(payouts['2']['show'], 3.40)
        self.assertIsNone(payouts['2']['win'])
        
        self.assertEqual(payouts['3']['show'], 2.10)

if __name__ == '__main__':
    unittest.main()
