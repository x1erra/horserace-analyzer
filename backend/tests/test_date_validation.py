
import unittest
import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from crawl_scratches import (
    LEGACY_LATE_CHANGES_TRACK_URL,
    MOBILE_LATE_CHANGES_TRACK_URL,
    TVG_LATE_CHANGES_TRACK_URL,
    determine_change_type,
    fetch_direct_track_changes_page,
    fetch_static_page,
    normalize_change_description,
    parse_mobile_track_changes,
    parse_rss_changes,
    parse_track_changes,
)

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

    def test_direct_track_page_prefers_tvg_host(self):
        with patch("crawl_scratches.fetch_static_page", side_effect=["<html>ok</html>"]) as fetch_mock:
            html, source_url = fetch_direct_track_changes_page("GP")

        self.assertEqual(html, "<html>ok</html>")
        self.assertEqual(source_url, TVG_LATE_CHANGES_TRACK_URL.format(track_code="GP"))
        fetch_mock.assert_called_once_with(TVG_LATE_CHANGES_TRACK_URL.format(track_code="GP"))

    def test_direct_track_page_falls_back_to_legacy_host(self):
        with patch("crawl_scratches.fetch_static_page", side_effect=[None, "<html>ok</html>"]) as fetch_mock:
            html, source_url = fetch_direct_track_changes_page("GP")

        self.assertEqual(html, "<html>ok</html>")
        self.assertEqual(source_url, LEGACY_LATE_CHANGES_TRACK_URL.format(track_code="GP"))
        self.assertEqual(fetch_mock.call_count, 2)

    def test_fetch_static_page_uses_playwright_last(self):
        with patch("crawl_scratches.fetch_page_via_requests", return_value=None) as req_mock, \
             patch("crawl_scratches.fetch_page_via_cloudscraper", return_value=None) as cloud_mock, \
             patch("crawl_scratches.fetch_page_via_curl_cffi", return_value=None) as curl_mock, \
             patch("crawl_scratches.fetch_page_via_powershell", return_value=None) as pwsh_mock, \
             patch("crawl_scratches.fetch_page_via_selenium", return_value=None) as selenium_mock, \
             patch("crawl_scratches.fetch_page_via_playwright", return_value="<html>ok</html>") as playwright_mock:
            html = fetch_static_page("https://example.test/latechanges")

        self.assertEqual(html, "<html>ok</html>")
        req_mock.assert_called_once()
        cloud_mock.assert_called_once()
        curl_mock.assert_called_once()
        pwsh_mock.assert_called_once()
        selenium_mock.assert_called_once()
        playwright_mock.assert_called_once()

    def test_parse_mobile_track_changes(self):
        html = f"""
        <html><body>
        <div>TODAY'S SCRATCHES AND CHANGES</div>
        <table width="100%" bgcolor="#008000"><tr><td><font color="#ffffff"><b>Race 7</b></font></td></tr></table>
        <p><b># 4 Royal Salute:</b></p>
        <p><ChangeDescWeb><i>Scratched</i> - Veterinarian</ChangeDescWeb></p>
        <p>10:01 AM ET</p>
        <p><ChangeDescWeb>Temp Rail Distance set at 45 ft.</ChangeDescWeb></p>
        <p>Reported at Entry Time</p>
        </body></html>
        """
        changes = parse_mobile_track_changes(html, "GP")

        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["race_number"], 7)
        self.assertEqual(changes[0]["program_number"], "4")
        self.assertEqual(changes[0]["horse_name"], "royalsalute")
        self.assertEqual(changes[0]["change_type"], "Scratch")
        self.assertEqual(changes[0]["description"], "Scratched - Veterinarian")
        self.assertEqual(changes[1]["description"], "Temp Rail Distance set at 45 ft.")

    def test_gelding_note_is_classified_as_horse_note(self):
        self.assertEqual(
            determine_change_type("First Start Since Reported as Gelding - Y"),
            "Horse Note",
        )

    def test_normalize_change_description_dedupes_gelding_note_noise(self):
        self.assertEqual(
            normalize_change_description(
                "First Start Since Reported as Gelding; First Start Since Reported as Gelding - Y"
            ),
            "First Start Since Reported as Gelding",
        )

if __name__ == '__main__':
    unittest.main()
