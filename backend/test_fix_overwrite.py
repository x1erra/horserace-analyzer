
import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock selenium libraries BEFORE import
sys.modules['selenium'] = MagicMock()
sys.modules['selenium.webdriver'] = MagicMock()
sys.modules['selenium.webdriver.chrome.options'] = MagicMock()
sys.modules['selenium.webdriver.chrome.service'] = MagicMock()
sys.modules['selenium.webdriver.common.by'] = MagicMock()
sys.modules['selenium.webdriver.support.ui'] = MagicMock()
sys.modules['selenium.webdriver.support'] = MagicMock()

import datetime
from crawl_entries import insert_upcoming_race

class TestFixOverwrite(unittest.TestCase):

    def setUp(self):
        self.mock_supabase = MagicMock()
        self.mock_track_id = "track-123"
        
    @patch('crawl_entries.get_or_create_track')
    def test_post_time_not_overwritten_if_none(self, mock_get_track):
        # Setup
        mock_get_track.return_value = self.mock_track_id
        
        # Existing race found in DB
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'race-123',
            'race_status': 'upcoming',
            'post_time': '1:00 PM' # Existing valid time
        }]
        
        # New data has NO post_time (simulation of failed parse)
        race_data = {
            'race_number': 1,
            'post_time': None,
            'entries': []
        }
        
        # Execute
        insert_upcoming_race(self.mock_supabase, 'GP', datetime.date(2024, 1, 1), race_data)
        
        # Verify
        # Get the update call args
        # chain: table().update(DATA).eq().execute()
        update_call = self.mock_supabase.table.return_value.update.call_args
        if update_call:
            args, _ = update_call
            update_payload = args[0]
            print(f"Update Payload (None Case): {update_payload}")
            
            self.assertNotIn('post_time', update_payload, "post_time should NOT be in update payload if None")
        else:
            self.fail("Update was not called")

    @patch('crawl_entries.get_or_create_track')
    def test_post_time_updated_if_valid(self, mock_get_track):
        # Setup
        mock_get_track.return_value = self.mock_track_id
        
        # Existing race found
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'race-123',
            'race_status': 'upcoming',
            'post_time': 'old_time'
        }]
        
        # New data HAS post_time
        race_data = {
            'race_number': 1,
            'post_time': '2:30 PM',
            'entries': []
        }
        
        # Execute
        insert_upcoming_race(self.mock_supabase, 'GP', datetime.date(2024, 1, 1), race_data)
        
        # Verify
        update_call = self.mock_supabase.table.return_value.update.call_args
        if update_call:
            args, _ = update_call
            update_payload = args[0]
            print(f"Update Payload (Valid Case): {update_payload}")
            
            self.assertIn('post_time', update_payload, "post_time SHOULD be in update payload if valid")
            self.assertEqual(update_payload['post_time'], '2:30 PM')
        else:
            self.fail("Update was not called")

if __name__ == '__main__':
    unittest.main()
