import os
import sys
import unittest
import types
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

supabase_stub = types.ModuleType("supabase")
supabase_stub.create_client = MagicMock()
supabase_stub.Client = object
sys.modules.setdefault("supabase", supabase_stub)

import mcp_server


class Response:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class QueryStub:
    def __init__(self, response):
        self.response = response

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def ilike(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        return self.response


class SupabaseStub:
    def __init__(self, response):
        self.response = response

    def table(self, _name):
        return QueryStub(self.response)


class TestMcpServer(unittest.TestCase):
    def test_expected_tool_surface_exists(self):
        expected_tools = {
            "get_health",
            "get_tracks",
            "get_recent_uploads",
            "get_filter_options",
            "get_todays_races",
            "get_past_races",
            "get_race_details",
            "get_horses",
            "get_horse_profile",
            "get_scratches",
            "get_changes",
            "get_race_changes",
            "get_claims",
        }

        for tool_name in expected_tools:
            self.assertTrue(hasattr(mcp_server, tool_name), f"Missing MCP tool function: {tool_name}")

    def test_get_changes_maps_view_all_to_history_mode(self):
        with patch.object(mcp_server, "fetch_change_feed", return_value={"changes": [], "count": 0}) as mock_feed:
            result = mcp_server.get_changes(view="all", page=2, limit=15, track="GP")

        self.assertEqual(result["count"], 0)
        mock_feed.assert_called_once_with(mode="history", page=2, limit=15, track="GP")

    def test_get_horse_profile_requires_identifier(self):
        with patch.object(mcp_server, "get_supabase_client", return_value=SupabaseStub(Response(data=[]))):
            result = mcp_server.get_horse_profile()
        self.assertEqual(result["error"], "Provide either horse_id or horse_name")

    def test_get_horse_profile_returns_matches_when_name_is_ambiguous(self):
        ambiguous_matches = [
            {
                "id": "horse-1",
                "horse_name": "Lightning Run",
                "sire": "Sire A",
                "dam": "Dam A",
                "color": "Bay",
                "sex": "G",
                "foaling_year": 2021,
            },
            {
                "id": "horse-2",
                "horse_name": "Lightning Run",
                "sire": "Sire B",
                "dam": "Dam B",
                "color": "Chestnut",
                "sex": "M",
                "foaling_year": 2020,
            },
        ]
        supabase = SupabaseStub(Response(data=ambiguous_matches))

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_horse_profile(horse_name="Lightning Run")

        self.assertIn("Multiple horses matched", result["error"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["matches"], ambiguous_matches)

    def test_get_health_returns_unhealthy_on_connection_failure(self):
        with patch.object(mcp_server, "get_supabase_client", side_effect=ValueError("missing key")):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("missing key", result["error"])


if __name__ == "__main__":
    unittest.main()
