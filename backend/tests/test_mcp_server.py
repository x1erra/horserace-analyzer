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


class SequenceQueryStub:
    def __init__(self, owner):
        self.owner = owner

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
        index = min(self.owner.index, len(self.owner.responses) - 1)
        response = self.owner.responses[index]
        self.owner.index += 1
        return response


class SequenceSupabaseStub:
    def __init__(self, responses):
        self.responses = list(responses)
        self.index = 0

    def table(self, _name):
        return SequenceQueryStub(self)


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
            "get_feed_freshness",
            "get_tracks",
            "get_recent_uploads",
            "get_filter_options",
            "get_entries",
            "get_results",
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

    def test_filter_options_include_canonical_woodbine(self):
        tracks = mcp_server._with_canonical_track_options(
            [
                {"name": "Gulfstream Park", "code": "GP"},
                {"name": "WO", "code": "WO"},
            ]
        )

        self.assertIn({"name": "Woodbine", "code": "WO"}, tracks)

    def test_get_feed_freshness_surfaces_open_alerts(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:04:07Z"},
                    "results": {"stale": True, "in_progress": False, "within_startup_grace": False, "last_success_at": None},
                },
                [
                    {"key": "crawl-stale:results", "status": "open"},
                    {"key": "crawl-stale:entries", "status": "resolved"},
                ],
            ),
        ), patch.object(
            mcp_server,
            "_detect_pipeline_activity",
            return_value={
                "entries_data_present": False,
                "results_data_present": False,
                "scratches_data_present": False,
                "any_recent_data": False,
                "active_signals": [],
            },
        ):
            result = mcp_server.get_feed_freshness()

        self.assertEqual(result["status"], "attention_needed")
        self.assertIn("results", result["crawler_summary"]["attention_needed"])
        self.assertEqual(result["crawlers"]["entries"]["status"], "ok")
        self.assertEqual(result["crawlers"]["results"]["status"], "attention_needed")
        self.assertIn("No recent successful results crawl", result["crawlers"]["results"]["reason"])
        self.assertEqual(result["open_alert_count"], 1)
        self.assertEqual(result["open_alerts"][0]["key"], "crawl-stale:results")
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("Trust status first", result["how_to_read"])
        self.assertEqual(result["tool_alias"], "get_feed_freshness")
        self.assertEqual(result["canonical_tool"], "get_health")
        self.assertTrue(result["deprecated"])

    def test_get_feed_freshness_reports_startup_grace_clearly(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": True, "last_success_at": None},
                    "results": {"stale": False, "in_progress": False, "within_startup_grace": True, "last_success_at": None},
                    "scratches": {"stale": False, "in_progress": False, "within_startup_grace": True, "last_success_at": None},
                },
                [],
            ),
        ), patch.object(
            mcp_server,
            "_detect_pipeline_activity",
            return_value={
                "entries_data_present": True,
                "results_data_present": True,
                "scratches_data_present": True,
                "any_recent_data": True,
                "active_signals": ["entries", "results", "scratches"],
            },
        ):
            result = mcp_server.get_feed_freshness()

        self.assertEqual(result["status"], "starting")
        self.assertEqual(set(result["crawler_summary"]["starting"]), {"entries", "results", "scratches"})
        self.assertFalse(result["legacy_compatibility"]["all_crawlers_fresh"])
        self.assertEqual(result["risk_level"], "low")
        self.assertIn("Wait for the first full crawler pass", result["recommended_action"])
        self.assertEqual(result["crawlers"]["entries"]["timestamps"]["state"], "pending_first_success")

    def test_get_feed_freshness_reports_recovering_when_data_exists(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": True, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T10:00:00Z"},
                    "results": {"stale": True, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T10:00:00Z"},
                    "scratches": {"stale": True, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T10:00:00Z"},
                },
                [],
            ),
        ):
            result = mcp_server.get_feed_freshness()

        self.assertEqual(result["status"], "recovering")
        self.assertEqual(set(result["crawler_summary"]["recovering"]), {"entries", "results", "scratches"})
        self.assertIn("still catching up", result["summary"])
        self.assertTrue(result["pipeline_activity"]["any_recent_data"])
        self.assertEqual(result["risk_level"], "low")
        self.assertIn("crawler freshness timestamps are still catching up", result["recommended_action"])
        self.assertEqual(result["crawlers"]["entries"]["status"], "recovering")
        self.assertEqual(result["crawlers"]["entries"]["timestamps"]["state"], "recorded")

    def test_get_health_returns_same_one_stop_report_shape(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:04:07Z", "last_attempt_at": "2026-04-03T04:04:07Z"},
                    "results": {"stale": False, "in_progress": True, "within_startup_grace": False, "last_success_at": "2026-04-03T04:00:00Z", "last_attempt_at": "2026-04-03T04:05:00Z", "last_error": "The read operation timed out"},
                    "scratches": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:03:00Z", "last_attempt_at": "2026-04-03T04:03:00Z"},
                },
                [],
            ),
        ), patch.object(
            mcp_server,
            "_detect_pipeline_activity",
            return_value={
                "entries_data_present": True,
                "results_data_present": True,
                "scratches_data_present": True,
                "any_recent_data": True,
                "active_signals": ["entries", "results", "scratches"],
            },
        ), patch.object(
            mcp_server,
            "probe_database_health",
            return_value={"status": "connected", "label": "Connected", "message": "Successfully queried the primary database.", "error": None},
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["database"]["status"], "connected")
        self.assertEqual(result["crawlers"]["results"]["status"], "running")
        self.assertEqual(result["status_label"], "Healthy")
        self.assertNotIn("last_error", result["crawlers"]["results"])
        self.assertNotIn("current_issue", result["crawlers"]["results"])
        self.assertEqual(
            result["crawlers"]["results"]["recent_incident"]["message"],
            "The database request timed out.",
        )
        self.assertTrue(result["crawlers"]["results"]["recent_incident"]["historical"])

    def test_get_health_treats_recent_pdf_scratch_evidence_as_healthy(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:04:07Z", "last_attempt_at": "2026-04-03T04:04:07Z"},
                    "results": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:00:00Z", "last_attempt_at": "2026-04-03T04:05:00Z"},
                    "scratches": {
                        "stale": False,
                        "in_progress": False,
                        "within_startup_grace": False,
                        "last_success_at": None,
                        "effective_last_success_at": "2026-04-03T04:03:00Z",
                        "last_attempt_at": "2026-04-03T03:40:00Z",
                        "last_observed_at": "2026-04-03T04:03:00Z",
                        "last_observed_source": "results_pdf_inferred",
                        "observation_supporting_freshness": True,
                    },
                },
                [],
            ),
        ), patch.object(
            mcp_server,
            "probe_database_health",
            return_value={"status": "connected", "label": "Connected", "message": "Successfully queried the primary database.", "error": None},
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["crawlers"]["scratches"]["status"], "ok")
        self.assertEqual(result["pipeline_activity"]["scratches_data_present"], True)
        self.assertEqual(result["crawlers"]["scratches"]["timestamps"]["state"], "observed_via_alternate_source")
        self.assertEqual(result["crawlers"]["scratches"]["evidence"]["last_observed_source"], "results_pdf_inferred")

    def test_get_changes_maps_view_all_to_all_mode(self):
        with patch.object(mcp_server, "fetch_change_feed", return_value={"changes": [], "count": 0}) as mock_feed:
            result = mcp_server.get_changes(view="all", page=2, limit=15, track="GP")

        self.assertEqual(result["count"], 0)
        mock_feed.assert_called_once_with(
            mode="all",
            page=2,
            limit=15,
            track="GP",
            start_date="",
            end_date="",
            race_number=0,
            include_race_wide=False,
        )

    def test_get_changes_falls_back_to_all_when_upcoming_is_empty(self):
        with patch.object(
            mcp_server,
            "fetch_change_feed",
            side_effect=[
                {"changes": [], "count": 0, "page": 1, "limit": 20, "total_pages": 0},
                {
                    "changes": [{"race_date": "2026-03-27", "track_code": "GP", "race_number": 1}],
                    "count": 1,
                    "page": 1,
                    "limit": 20,
                    "total_pages": 1,
                },
            ],
        ) as mock_feed:
            result = mcp_server.get_changes()

        self.assertEqual(result["count"], 1)
        self.assertTrue(result["meta"]["fallback_applied"])
        self.assertEqual(result["meta"]["applied_view"], "all")
        self.assertIn("historical changes", result["meta"]["fallback_reason"])
        self.assertEqual(mock_feed.call_count, 2)

    def test_get_changes_passes_date_filters_through(self):
        with patch.object(mcp_server, "fetch_change_feed", return_value={"changes": [], "count": 0}) as mock_feed:
            mcp_server.get_changes(view="all", start_date="2026-03-01", end_date="2026-03-31", track="SA")

        mock_feed.assert_called_once_with(
            mode="all",
            page=1,
            limit=20,
            track="SA",
            start_date="2026-03-01",
            end_date="2026-03-31",
            race_number=0,
            include_race_wide=False,
        )

    def test_get_changes_passes_race_number_through(self):
        with patch.object(mcp_server, "fetch_change_feed", return_value={"changes": [], "count": 0}) as mock_feed:
            mcp_server.get_changes(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)

        mock_feed.assert_called_once_with(
            mode="upcoming",
            page=1,
            limit=20,
            track="GP",
            start_date="2026-04-06",
            end_date="2026-04-06",
            race_number=4,
            include_race_wide=False,
        )

    def test_get_changes_hides_race_wide_by_default_and_can_include_it(self):
        with patch.object(
            mcp_server,
            "fetch_change_feed",
            side_effect=[
                {
                    "changes": [{"id": "chg-1", "horse_name": "Horse A"}],
                    "count": 1,
                    "page": 1,
                    "limit": 20,
                    "total_pages": 1,
                    "has_more": False,
                },
                {
                    "changes": [{"id": "chg-1", "horse_name": "Horse A"}],
                    "count": 1,
                    "page": 1,
                    "limit": 20,
                    "total_pages": 1,
                    "has_more": False,
                },
            ],
        ) as mock_feed:
            default_result = mcp_server.get_changes(track="SA")
            visible_result = mcp_server.get_changes(track="SA", include_race_wide=True)

        first_call = mock_feed.call_args_list[0]
        second_call = mock_feed.call_args_list[1]
        self.assertEqual(first_call.kwargs["include_race_wide"], False)
        self.assertEqual(second_call.kwargs["include_race_wide"], True)
        self.assertTrue(default_result["meta"]["race_wide_hidden"])
        self.assertFalse(visible_result["meta"]["race_wide_hidden"])

    def test_get_scratches_falls_back_to_all_when_upcoming_is_empty(self):
        with patch.object(
            mcp_server,
            "fetch_scratch_feed",
            side_effect=[
                {"scratches": [], "count": 0, "page": 1, "limit": 20, "total_pages": 0},
                {
                    "scratches": [
                        {
                            "id": "entry-1",
                            "race_date": "2026-03-27",
                            "track_code": "SA",
                            "track_name": "Santa Anita",
                            "race_number": 3,
                            "post_time": "2:00 PM",
                            "program_number": "5",
                            "horse_name": "A Lister",
                            "trainer_name": "Bob Baffert",
                            "status": "Scratched",
                        }
                    ],
                    "count": 1,
                    "page": 1,
                    "limit": 20,
                    "total_pages": 1,
                },
            ],
        ):
            result = mcp_server.get_scratches()

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["scratches"][0]["horse_name"], "A Lister")
        self.assertTrue(result["meta"]["fallback_applied"])
        self.assertEqual(result["meta"]["applied_view"], "all")
        self.assertIn("historical scratches", result["meta"]["fallback_reason"])

    def test_get_scratches_filters_by_race_number(self):
        with patch.object(
            mcp_server,
            "fetch_scratch_feed",
            return_value={
                "scratches": [
                    {
                        "id": "entry-1",
                        "race_date": "2026-04-06",
                        "track_code": "GP",
                        "track_name": "Gulfstream Park",
                        "race_number": 4,
                        "post_time": "2:00 PM",
                        "program_number": "5",
                        "horse_name": "Race Four Horse",
                        "trainer_name": "Trainer A",
                        "status": "Scratched",
                    }
                ],
                "count": 1,
                "page": 1,
                "limit": 20,
                "total_pages": 1,
            },
        ) as mock_feed:
            result = mcp_server.get_scratches(view="all", track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)

        mock_feed.assert_called_once_with(
            mode="all",
            page=1,
            limit=20,
            track="GP",
            start_date="2026-04-06",
            end_date="2026-04-06",
            race_number=4,
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["scratches"][0]["horse_name"], "Race Four Horse")
        self.assertEqual(result["scratches"][0]["race_number"], 4)

    def test_fetch_scratch_feed_uses_normalized_change_feed(self):
        with patch.object(
            mcp_server,
            "fetch_change_feed",
            return_value={
                "changes": [
                    {
                        "id": "chg-1",
                        "entry_id": "entry-1",
                        "race_id": "race-1",
                        "race_key": "GP-20260403-4",
                        "race_date": "2026-04-03",
                        "track_code": "GP",
                        "track_name": "Gulfstream Park",
                        "race_number": 4,
                        "post_time": "14:00:00",
                        "program_number": "5",
                        "horse_name": "Scratch Horse",
                        "trainer_name": "Trainer A",
                        "change_type": "Scratch",
                        "description": "Veterinarian",
                        "change_time": "2026-04-03T12:00:00Z",
                    },
                    {
                        "id": "chg-2",
                        "entry_id": "entry-2",
                        "race_id": "race-1",
                        "race_key": "GP-20260403-4",
                        "race_date": "2026-04-03",
                        "track_code": "GP",
                        "track_name": "Gulfstream Park",
                        "race_number": 4,
                        "post_time": "14:00:00",
                        "program_number": "6",
                        "horse_name": "Weight Horse",
                        "trainer_name": "Trainer B",
                        "change_type": "Weight Change",
                        "description": "+2 lbs",
                        "change_time": "2026-04-03T12:05:00Z",
                    },
                ],
                "count": 2,
                "page": 1,
                "limit": 10000,
                "total_pages": 1,
            },
        ):
            result = mcp_server.fetch_scratch_feed(track="GP", start_date="2026-04-03", end_date="2026-04-03", race_number=4)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["scratches"][0]["horse_name"], "Scratch Horse")
        self.assertEqual(result["scratches"][0]["description"], "Veterinarian")
        self.assertEqual(result["scratches"][0]["change_type"], "Scratch")

    def test_get_entries_filters_track_date_and_race_number(self):
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "GP-20260406-4",
                        "track_code": "GP",
                        "race_date": "2026-04-06",
                        "race_number": 4,
                        "post_time": "14:00:00",
                        "race_type": "Allowance",
                        "surface": "Dirt",
                        "distance": "6 Furlongs",
                        "purse": "$44,000",
                        "race_status": "upcoming",
                        "hranalyzer_tracks": {"track_name": "Gulfstream Park", "timezone": "America/New_York"},
                    },
                    {
                        "id": "race-2",
                        "race_key": "GP-20260406-5",
                        "track_code": "GP",
                        "race_date": "2026-04-06",
                        "race_number": 5,
                        "post_time": "14:30:00",
                        "race_type": "Claiming",
                        "surface": "Turf",
                        "distance": "1 Mile",
                        "purse": "$20,000",
                        "race_status": "upcoming",
                        "hranalyzer_tracks": {"track_name": "Gulfstream Park", "timezone": "America/New_York"},
                    },
                ],
                "hranalyzer_race_entries": [
                    {
                        "id": "entry-1",
                        "race_id": "race-1",
                        "program_number": "5",
                        "post_position": 5,
                        "morning_line_odds": "4/1",
                        "final_odds": None,
                        "scratched": False,
                        "weight": 122,
                        "medication": "L",
                        "equipment": "b",
                        "hranalyzer_horses": {"horse_name": "Target Horse"},
                        "hranalyzer_jockeys": {"jockey_name": "Jockey A"},
                        "hranalyzer_trainers": {"trainer_name": "Trainer A"},
                    },
                    {
                        "id": "entry-2",
                        "race_id": "race-2",
                        "program_number": "6",
                        "post_position": 6,
                        "morning_line_odds": "6/1",
                        "final_odds": None,
                        "scratched": False,
                        "weight": 120,
                        "medication": None,
                        "equipment": None,
                        "hranalyzer_horses": {"horse_name": "Other Horse"},
                        "hranalyzer_jockeys": {"jockey_name": "Jockey B"},
                        "hranalyzer_trainers": {"trainer_name": "Trainer B"},
                    },
                ],
            }
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_entries(track="GP", race_date="2026-04-06", race_number=4)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["race_key"], "GP-20260406-4")
        self.assertEqual(result["entries"][0]["entries"][0]["horse_name"], "Target Horse")

    def test_get_results_filters_track_date_and_race_number(self):
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "GP-20260406-4",
                        "track_code": "GP",
                        "race_date": "2026-04-06",
                        "race_number": 4,
                        "post_time": "14:00:00",
                        "race_status": "completed",
                        "final_time": "1:10.55",
                        "winner_program_number": "5",
                        "hranalyzer_tracks": {"track_name": "Gulfstream Park", "timezone": "America/New_York"},
                    },
                    {
                        "id": "race-2",
                        "race_key": "GP-20260406-5",
                        "track_code": "GP",
                        "race_date": "2026-04-06",
                        "race_number": 5,
                        "post_time": "14:30:00",
                        "race_status": "completed",
                        "final_time": "1:35.10",
                        "winner_program_number": "6",
                        "hranalyzer_tracks": {"track_name": "Gulfstream Park", "timezone": "America/New_York"},
                    },
                ],
                "hranalyzer_race_entries": [
                    {
                        "race_id": "race-1",
                        "program_number": "5",
                        "finish_position": 1,
                        "final_odds": "3.20",
                        "win_payout": "8.40",
                        "place_payout": "4.20",
                        "show_payout": "2.80",
                        "hranalyzer_horses": {"horse_name": "Winner Horse"},
                        "hranalyzer_trainers": {"trainer_name": "Trainer A"},
                    },
                    {
                        "race_id": "race-2",
                        "program_number": "6",
                        "finish_position": 1,
                        "final_odds": "4.10",
                        "win_payout": "10.20",
                        "place_payout": "5.00",
                        "show_payout": "3.10",
                        "hranalyzer_horses": {"horse_name": "Other Winner"},
                        "hranalyzer_trainers": {"trainer_name": "Trainer B"},
                    },
                ],
            }
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_results(track="GP", race_date="2026-04-06", race_number=4)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["race_key"], "GP-20260406-4")
        self.assertEqual(result["results"][0]["winner"], "Winner Horse")

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

    def test_get_horse_profile_returns_alias_fields(self):
        supabase = SequenceSupabaseStub(
            [
                Response(
                    data={
                        "id": "horse-1",
                        "horse_name": "Lightning Run",
                        "sire": "Sire A",
                        "dam": "Dam A",
                        "color": "Bay",
                        "sex": "G",
                        "foaling_year": 2021,
                    }
                ),
                Response(
                    data=[
                        {
                            "id": "entry-1",
                            "program_number": "5",
                            "finish_position": 1,
                            "final_odds": "2.5",
                            "win_payout": "7.80",
                            "place_payout": "4.20",
                            "show_payout": "2.80",
                            "scratched": False,
                            "run_comments": "Clear trip",
                            "race": {
                                "race_key": "GP-20260406-4",
                                "race_date": "2026-04-06",
                                "race_number": 4,
                                "track_code": "GP",
                                "race_type": "Allowance",
                                "surface": "Dirt",
                                "distance": "6 Furlongs",
                                "purse": "$44,000",
                                "race_status": "completed",
                                "track": {"track_name": "Gulfstream Park"},
                            },
                            "jockey": {"jockey_name": "Jockey A"},
                            "trainer": {"trainer_name": "Trainer A"},
                        }
                    ]
                ),
            ]
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_horse_profile(horse_id="horse-1")

        self.assertEqual(result["horse"]["name"], "Lightning Run")
        self.assertEqual(result["horse"]["horse_name"], "Lightning Run")
        self.assertEqual(result["recent_races"], result["race_history"])

    def test_get_race_details_includes_entries_alias_inside_race(self):
        supabase = SequenceSupabaseStub(
            [
                Response(
                    data={
                        "id": "race-1",
                        "race_key": "GP-20260406-4",
                        "track_code": "GP",
                        "race_date": "2026-04-06",
                        "race_number": 4,
                        "post_time": "14:00:00",
                        "race_type": "Allowance",
                        "surface": "Dirt",
                        "distance": "6 Furlongs",
                        "distance_feet": 3960,
                        "conditions": "NW1X",
                        "purse": "$44,000",
                        "race_status": "upcoming",
                        "data_source": "equibase",
                        "final_time": None,
                        "fractional_times": None,
                        "equibase_chart_url": None,
                        "equibase_pdf_url": None,
                        "hranalyzer_tracks": {
                            "track_name": "Gulfstream Park",
                            "location": "Hallandale Beach, FL",
                            "timezone": "America/New_York",
                        },
                    }
                ),
                Response(
                    data=[
                        {
                            "id": "entry-1",
                            "program_number": "5",
                            "post_position": 5,
                            "hranalyzer_horses": {"horse_name": "Target Horse", "sire": None, "dam": None, "color": "Bay", "sex": "G"},
                            "hranalyzer_jockeys": {"jockey_name": "Jockey A"},
                            "hranalyzer_trainers": {"trainer_name": "Trainer A"},
                            "hranalyzer_owners": {"owner_name": "Owner A"},
                        }
                    ]
                ),
                Response(data=[]),
            ]
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_race_details("GP-20260406-4")

        self.assertEqual(result["entries"][0]["horse_name"], "Target Horse")
        self.assertEqual(result["race"]["entries"][0]["horse_name"], "Target Horse")

    def test_get_health_returns_unhealthy_on_connection_failure(self):
        with patch.object(
            mcp_server,
            "probe_database_health",
            return_value={
                "status": "disconnected",
                "label": "Disconnected",
                "message": "The primary database check failed.",
                "error": "missing key",
            },
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(result["database"]["status"], "disconnected")
        self.assertIn("missing key", result["database"]["error"])

    def test_get_health_ignores_cached_disconnected_snapshot_when_live_probe_recovers(self):
        with patch.object(
            mcp_server,
            "get_database_health_snapshot",
            return_value={
                "status": "disconnected",
                "label": "Disconnected",
                "message": "The primary database check failed.",
                "error": "old failure",
                "checked_at": "2026-04-07T21:00:00Z",
            },
        ), patch.object(
            mcp_server,
            "probe_database_health",
            return_value={
                "status": "connected",
                "label": "Connected",
                "message": "Successfully queried the primary database.",
                "error": None,
            },
        ), patch.object(
            mcp_server,
            "get_recent_boot_at",
            return_value=None,
        ), patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:08:14Z"},
                    "results": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:35:44Z"},
                    "scratches": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:38:29Z"},
                },
                [],
            ),
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["database"]["status"], "connected")

    def test_get_health_ignores_pre_boot_database_snapshot(self):
        with patch.object(
            mcp_server,
            "get_database_health_snapshot",
            return_value={
                "status": "disconnected",
                "label": "Disconnected",
                "message": "The primary database check failed.",
                "error": "before reboot",
                "checked_at": "2026-04-07T20:00:00Z",
            },
        ), patch.object(
            mcp_server,
            "get_recent_boot_at",
            return_value=mcp_server.parse_iso("2026-04-07T21:07:18Z"),
        ), patch.object(
            mcp_server,
            "probe_database_health",
            return_value={
                "status": "connected",
                "label": "Connected",
                "message": "Successfully queried the primary database.",
                "error": None,
            },
        ), patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:08:14Z"},
                    "results": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:35:44Z"},
                    "scratches": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-07T21:38:29Z"},
                },
                [],
            ),
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["database"]["status"], "connected")

    def test_get_health_keeps_active_issue_for_attention_needed_crawler(self):
        with patch.object(
            mcp_server,
            "summarize_freshness",
            return_value=(
                {
                    "entries": {
                        "stale": True,
                        "in_progress": False,
                        "within_startup_grace": False,
                        "last_success_at": None,
                        "last_attempt_at": "2026-04-03T04:05:00Z",
                        "last_error": "Error code 521",
                        "last_details": {"phase": "today"},
                    },
                    "results": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:00:00Z"},
                    "scratches": {"stale": False, "in_progress": False, "within_startup_grace": False, "last_success_at": "2026-04-03T04:03:00Z"},
                },
                [],
            ),
        ), patch.object(
            mcp_server,
            "probe_database_health",
            return_value={"status": "connected", "label": "Connected", "message": "Successfully queried the primary database.", "error": None},
        ):
            result = mcp_server.get_health()

        self.assertEqual(result["status"], "attention_needed")
        self.assertEqual(
            result["crawlers"]["entries"]["current_issue"],
            "Supabase upstream returned Cloudflare 521 (web server down).",
        )
        self.assertNotIn("recent_incident", result["crawlers"]["entries"])
        self.assertEqual(result["crawlers"]["entries"]["last_details"], {"phase": "today"})

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

    def test_get_changes_history_uses_incremental_paging(self):
        history_date = "2026-03-30"
        change_rows = [
            {
                "id": f"chg-{idx}",
                "entry_id": f"entry-{idx}",
                "race_id": "race-1",
                "change_type": "Jockey Change",
                "description": f"Jockey changed to Rider {idx}",
                "created_at": f"2026-03-30T12:{idx % 60:02d}:00Z",
                "race": {"id": "race-1", "race_date": history_date, "track_code": "SA"},
            }
            for idx in range(101)
        ]
        entry_rows = [
            {
                "id": f"entry-{idx}",
                "race_id": "race-1",
                "program_number": str(idx + 1),
                "weight": 124,
                "horse": {"horse_name": f"Horse {idx}"},
                "jockey": {"jockey_name": f"Rider {idx}"},
                "trainer": {"trainer_name": "Trainer A"},
            }
            for idx in range(101)
        ]
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": change_rows,
                "hranalyzer_race_entries": entry_rows,
                "hranalyzer_races": [
                    {
                        "id": "race-1",
                        "race_key": "SA-20260331-3",
                        "track_code": "SA",
                        "race_date": history_date,
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
            result = mcp_server.get_changes(view="history", track="SA", page=1, limit=20)

        self.assertEqual(len(result["changes"]), 20)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["page"], 1)

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
        self.assertTrue(result["meta"]["race_wide_hidden"])

    def test_get_race_changes_filters_blank_race_wide_noise(self):
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": [
                    {
                        "id": "chg-noise",
                        "entry_id": None,
                        "race_id": "race-1",
                        "change_type": "Other",
                        "description": "",
                        "created_at": "2026-03-31T12:00:00Z",
                    },
                    {
                        "id": "chg-real",
                        "entry_id": None,
                        "race_id": "race-1",
                        "change_type": "Post Time Change",
                        "description": "Post time delayed to 2:15 PM",
                        "created_at": "2026-03-31T12:05:00Z",
                    },
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
            result = mcp_server.get_race_changes("race-1", include_race_wide=True)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["changes"][0]["change_type"], "Post Time Change")

    def test_get_race_changes_hides_race_wide_by_default_and_can_include_it(self):
        supabase = SupabaseRouterStub(
            {
                "hranalyzer_changes": [
                    {
                        "id": "chg-race-wide",
                        "entry_id": None,
                        "race_id": "race-1",
                        "change_type": "Track Condition",
                        "description": "Track changed to Fast",
                        "created_at": "2026-03-31T12:00:00Z",
                    },
                    {
                        "id": "chg-horse",
                        "entry_id": "entry-1",
                        "race_id": "race-1",
                        "change_type": "Jockey Change",
                        "description": "Jockey changed to Jane Doe",
                        "created_at": "2026-03-31T12:01:00Z",
                    },
                ],
                "hranalyzer_race_entries": [
                    {
                        "id": "entry-1",
                        "race_id": "race-1",
                        "program_number": "5",
                        "weight": 124,
                        "horse": {"horse_name": "Horse A"},
                        "jockey": {"jockey_name": "Jane Doe"},
                        "trainer": {"trainer_name": "Trainer A"},
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
            default_result = mcp_server.get_race_changes("race-1")
            full_result = mcp_server.get_race_changes("race-1", include_race_wide=True)

        self.assertEqual(default_result["count"], 1)
        self.assertEqual(default_result["changes"][0]["horse_name"], "Horse A")
        self.assertEqual(full_result["count"], 2)
        self.assertFalse(full_result["meta"]["race_wide_hidden"])

    def test_get_claims_filters_by_race_number(self):
        supabase = SupabaseStub(
            Response(
                data=[
                    {
                        "id": "claim-1",
                        "horse_name": "Horse A",
                        "program_number": "5",
                        "new_trainer_name": "Trainer A",
                        "new_owner_name": "Owner A",
                        "claim_price": 25000,
                        "hranalyzer_races": {
                            "race_key": "GP-20260406-4",
                            "track_code": "GP",
                            "race_date": "2026-04-06",
                            "race_number": 4,
                            "hranalyzer_tracks": {"track_name": "Gulfstream Park"},
                        },
                    },
                    {
                        "id": "claim-2",
                        "horse_name": "Horse B",
                        "program_number": "2",
                        "new_trainer_name": "Trainer B",
                        "new_owner_name": "Owner B",
                        "claim_price": 32000,
                        "hranalyzer_races": {
                            "race_key": "GP-20260406-5",
                            "track_code": "GP",
                            "race_date": "2026-04-06",
                            "race_number": 5,
                            "hranalyzer_tracks": {"track_name": "Gulfstream Park"},
                        },
                    },
                ]
            )
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_claims(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["claims"][0]["race_number"], 4)
        self.assertEqual(result["claims"][0]["horse_name"], "Horse A")
        self.assertTrue(result["claims"][0]["claimant_details_complete"])
        self.assertEqual(result["meta"]["missing_claimant_details"], 0)
        self.assertEqual(result["meta"]["claims_with_complete_details"], 1)
        self.assertEqual(result["meta"]["claimant_detail_coverage_pct"], 100.0)

    def test_get_claims_reports_missing_claimant_details(self):
        supabase = SupabaseStub(
            Response(
                data=[
                    {
                        "id": "claim-1",
                        "horse_name": "Horse A",
                        "program_number": "5",
                        "new_trainer_name": "",
                        "new_owner_name": None,
                        "claim_price": 25000,
                        "hranalyzer_races": {
                            "race_key": "GP-20260406-4",
                            "track_code": "GP",
                            "race_date": "2026-04-06",
                            "race_number": 4,
                            "hranalyzer_tracks": {"track_name": "Gulfstream Park"},
                        },
                    }
                ]
            )
        )

        with patch.object(mcp_server, "get_supabase_client", return_value=supabase):
            result = mcp_server.get_claims(track="GP", start_date="2026-04-06", end_date="2026-04-06", race_number=4)

        self.assertEqual(result["count"], 1)
        self.assertFalse(result["claims"][0]["claimant_details_complete"])
        self.assertEqual(result["meta"]["missing_claimant_details"], 1)
        self.assertFalse(result["meta"]["all_claimant_details_complete"])
        self.assertEqual(result["meta"]["claims_with_complete_details"], 0)
        self.assertEqual(result["meta"]["claimant_detail_coverage_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
