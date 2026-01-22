
import unittest
import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import parse_rss_changes, parse_track_changes

class TestDateValidation(unittest.TestCase):
    
    def test_rss_date_validation(self):
        """Test that RSS parser respects pubDate"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Format: "Thu, 22 Jan 2026 09:30:00 EST"
        # We need the correct day of week for the format to be robustly parsed by email.utils?
        # Actually email.utils is flexible.
        today_str = today.strftime("%a, %d %b %Y 12:00:00 EST")
        yesterday_str = yesterday.strftime("%a, %d %b %Y 12:00:00 EST")
        
        xml = f"""
        <rss>
            <channel>
                <item>
                    <description>Race 1: Race Cancelled - Test</description>
                    <pubDate>{today_str}</pubDate>
                </item>
                <item>
                    <description>Race 2: Race Cancelled - Old</description>
                    <pubDate>{yesterday_str}</pubDate>
                </item>
            </channel>
        </rss>
        """
        
        changes = parse_rss_changes(xml, 'TEST')
        
        # Should only have 1 item (today's)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['description'], 'Test')
        
    def test_html_date_validation_success(self):
        """Test HTML with correct date"""
        today = date.today()
        d_str = today.strftime("%B %d, %Y") # January 22, 2026
        
        html = f"""
        <html>
            <h3>Current Late Changes - {d_str}</h3>
            <table>
                <tr><th>Latest Changes</th></tr>
                <tr><th class="race">Race 1</th></tr>
                <tr><td class="changes">Race Cancelled</td></tr>
            </table>
        </html>
        """
        
        changes = parse_track_changes(html, 'TEST')
        self.assertTrue(len(changes) > 0)
        
    def test_html_date_validation_fail(self):
        """Test HTML with old date"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        d_str = yesterday.strftime("%B %d, %Y") 
        
        html = f"""
        <html>
            <h3>Current Late Changes - {d_str}</h3>
            <table>
                <tr><th class="race">Race 1</th></tr>
                <tr><td class="changes">Race Cancelled</td></tr>
            </table>
        </html>
        """
        
        changes = parse_track_changes(html, 'TEST')
        # Should reject entire page
        self.assertEqual(len(changes), 0)

if __name__ == '__main__':
    unittest.main()
