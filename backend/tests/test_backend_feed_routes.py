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


if __name__ == "__main__":
    unittest.main()
