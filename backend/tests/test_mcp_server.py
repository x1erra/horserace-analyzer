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


class FastMCPStub:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def run(self, *args, **kwargs):
        return None


mcp_stub = types.ModuleType("mcp")
mcp_server_stub = types.ModuleType("mcp.server")
mcp_fastmcp_stub = types.ModuleType("mcp.server.fastmcp")
mcp_fastmcp_stub.FastMCP = FastMCPStub
sys.modules.setdefault("mcp", mcp_stub)
sys.modules.setdefault("mcp.server", mcp_server_stub)
sys.modules.setdefault("mcp.server.fastmcp", mcp_fastmcp_stub)

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

    def in_(self, *args, **kwargs):
        return self

    def lt(self, *args, **kwargs):
        return self

    def lte(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def ilike(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
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


class QueryRouterStub:
    def __init__(self, rows, single=False):
        self.rows = list(rows)
        self.is_single = single
        self.range_start = None
        self.range_end = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if _resolve_field(row, field) == value]
        return self

    def in_(self, field, values):
        values = set(values)
        self.rows = [row for row in self.rows if _resolve_field(row, field) in values]
        return self

    def lt(self, field, value):
        self.rows = [row for row in self.rows if _resolve_field(row, field) < value]
        return self

    def lte(self, field, value):
        self.rows = [row for row in self.rows if _resolve_field(row, field) <= value]
        return self

    def gte(self, field, value):
        self.rows = [row for row in self.rows if _resolve_field(row, field) >= value]
        return self

    def ilike(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def single(self):
        self.is_single = True
        return self

    def execute(self):
        rows = self.rows
        if self.range_start is not None and self.range_end is not None:
            rows = rows[self.range_start:self.range_end + 1]
        if self.is_single:
            return Response(data=rows[0] if rows else None)
        return Response(data=rows)


class SupabaseRouterStub:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return QueryRouterStub(self.tables.get(name, []))


def _resolve_field(row, field):
    current = row
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


class FakeDate:
    @staticmethod
    def today():
        return types.SimpleNamespace(isoformat=lambda: "2026-03-31")


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

    def test_get_changes_bulk_hydrates_race_and_entry_context(self):
        today = "2026-03-31"
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": [
                    {
                        "id": "chg-1",
                        "entry_id": "entry-1",
                        "race_id": "race-1",
                        "change_type": "Jockey Change",
                        "description": "Jockey changed to Jane Doe",
                        "created_at": "2026-03-31T12:00:00Z",
                        "race": {"id": "race-1", "race_date": today, "track_code": "SA"},
                    }
                ],
                "hranalyzer_race_entries": [
                    {
                        "id": "entry-1",
                        "race_id": "race-1",
                        "program_number": "5",
                        "weight": 124,
                        "horse": {"horse_name": "A Lister"},
                        "jockey": {"jockey_name": "Jane Doe"},
                        "trainer": {"trainer_name": "Bob Baffert"},
                    }
                ],
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "SA-20260331-3",
                        "track_code": "SA",
                        "race_date": today,
                        "race_number": 3,
                        "post_time": "14:00:00",
                        "track": {"track_name": "Santa Anita"},
                    }
                ],
            }
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase), patch.object(
            mcp_server, "date", FakeDate
        ):
            result = mcp_server.get_changes(track="SA")

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["changes"][0]["horse_name"], "A Lister")
        self.assertEqual(result["changes"][0]["race_key"], "SA-20260331-3")
        self.assertEqual(result["changes"][0]["track_name"], "Santa Anita")
        self.assertEqual(result["changes"][0]["jockey_name"], "Jane Doe")
        self.assertEqual(result["changes"][0]["trainer_name"], "Bob Baffert")

    def test_get_changes_filters_orphan_horse_specific_rows(self):
        today = "2026-03-31"
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": [
                    {
                        "id": "chg-orphan",
                        "entry_id": None,
                        "race_id": "race-1",
                        "change_type": "Jockey Change",
                        "description": "Jockey changed to Jane Doe",
                        "created_at": "2026-03-31T12:00:00Z",
                        "race": {"id": "race-1", "race_date": today, "track_code": "SA"},
                    }
                ],
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "SA-20260331-3",
                        "track_code": "SA",
                        "race_date": today,
                        "race_number": 3,
                        "post_time": "14:00:00",
                        "track": {"track_name": "Santa Anita"},
                    }
                ],
            }
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase), patch.object(
            mcp_server, "date", FakeDate
        ):
            result = mcp_server.get_changes(track="SA")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["changes"], [])

    def test_get_race_changes_uses_created_at_and_bulk_hydration(self):
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": [
                    {
                        "id": "chg-1",
                        "entry_id": "entry-1",
                        "race_id": "race-1",
                        "change_type": "Jockey Change",
                        "description": "Jockey changed to Jane Doe",
                        "created_at": "2026-03-31T12:00:00Z",
                    }
                ],
                "hranalyzer_race_entries": [
                    {
                        "id": "entry-1",
                        "race_id": "race-1",
                        "program_number": "5",
                        "weight": 124,
                        "horse": {"horse_name": "A Lister"},
                        "jockey": {"jockey_name": "Jane Doe"},
                        "trainer": {"trainer_name": "Bob Baffert"},
                    }
                ],
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "SA-20260331-3",
                        "track_code": "SA",
                        "race_date": "2026-03-31",
                        "race_number": 3,
                        "post_time": "14:00:00",
                        "track": {"track_name": "Santa Anita"},
                    }
                ],
            }
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_race_changes("race-1")

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["changes"][0]["change_time"], "2026-03-31T12:00:00Z")
        self.assertEqual(result["changes"][0]["horse_name"], "A Lister")
        self.assertEqual(result["changes"][0]["race_key"], "SA-20260331-3")


if __name__ == "__main__":
    unittest.main()
