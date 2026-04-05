import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend import backend as backend_module


class TestBackendFeedRoutes(unittest.TestCase):
    def setUp(self):
        self.client = backend_module.app.test_client()

    def test_scratches_route_delegates_to_shared_mcp_logic(self):
        fake_module = types.SimpleNamespace(
            get_scratches=MagicMock(return_value={"scratches": [], "count": 0, "meta": {}})
        )

        with patch.dict(sys.modules, {"mcp_server": fake_module}):
            response = self.client.get(
                "/api/scratches?view=all&track=GP&start_date=2026-04-03&end_date=2026-04-03&race_number=7&page=2&limit=50"
            )

        self.assertEqual(response.status_code, 200)
        fake_module.get_scratches.assert_called_once_with(
            view="all",
            page=2,
            limit=50,
            track="GP",
            start_date="2026-04-03",
            end_date="2026-04-03",
            race_number=7,
        )

    def test_changes_route_delegates_to_shared_mcp_logic(self):
        fake_module = types.SimpleNamespace(
            get_changes=MagicMock(return_value={"changes": [], "count": 0, "meta": {}})
        )

        with patch.dict(sys.modules, {"mcp_server": fake_module}):
            response = self.client.get(
                "/api/changes?mode=all&track=GP&start_date=2026-04-03&end_date=2026-04-03&race_number=7&page=3&limit=25"
            )

        self.assertEqual(response.status_code, 200)
        fake_module.get_changes.assert_called_once_with(
            view="upcoming",
            mode="all",
            page=3,
            limit=25,
            track="GP",
            start_date="2026-04-03",
            end_date="2026-04-03",
            race_number=7,
        )

    def test_claims_route_delegates_to_shared_mcp_logic(self):
        fake_module = types.SimpleNamespace(
            get_claims=MagicMock(return_value={"claims": [], "count": 0, "meta": {}})
        )

        with patch.dict(sys.modules, {"mcp_server": fake_module}):
            response = self.client.get(
                "/api/claims?track=GP&start_date=2026-04-03&end_date=2026-04-03&race_number=7&limit=25"
            )

        self.assertEqual(response.status_code, 200)
        fake_module.get_claims.assert_called_once_with(
            track="GP",
            start_date="2026-04-03",
            end_date="2026-04-03",
            race_number=7,
            limit=25,
        )

    def test_todays_races_falls_back_to_snapshot_on_db_timeout(self):
        snapshot_payload = {
            "races": [
                {
                    "track_name": "Gulfstream Park",
                    "track_code": "GP",
                    "race_status": "upcoming",
                    "race_key": "GP-20260403-1",
                },
                {
                    "track_name": "Santa Anita",
                    "track_code": "SA",
                    "race_status": "completed",
                    "race_key": "SA-20260403-2",
                },
            ],
            "count": 2,
            "date": "2026-04-03",
        }

        with patch.object(backend_module, "get_supabase_client", side_effect=Exception("The read operation timed out")), patch.object(
            backend_module,
            "get_api_payload_snapshot",
            return_value={"captured_at": "2026-04-03T12:00:00Z", "payload": snapshot_payload},
        ):
            response = self.client.get("/api/todays-races?track=GP&status=Upcoming")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data_source"], "snapshot")
        self.assertTrue(payload["stale"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["races"][0]["track_code"], "GP")


if __name__ == "__main__":
    unittest.main()
