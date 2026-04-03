import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


class TestRuntimeState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["RUNTIME_STATE_DIR"] = self.temp_dir.name
        sys.modules.pop("runtime_state", None)
        sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
        self.runtime_state = importlib.import_module("runtime_state")

    def tearDown(self):
        os.environ.pop("RUNTIME_STATE_DIR", None)
        os.environ.pop("ALERT_WEBHOOK_URL", None)
        self.temp_dir.cleanup()

    def test_dashboard_snapshot_round_trip(self):
        payload = {"today_summary": [{"track_code": "MVR", "total": 8}]}
        self.runtime_state.snapshot_dashboard_summary("2026-04-02", payload)

        snapshot = self.runtime_state.get_dashboard_summary_snapshot("2026-04-02")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["payload"], payload)
        self.assertIn("captured_at", snapshot)

    def test_repeated_summary_failures_raise_alert(self):
        for idx in range(3):
            self.runtime_state.record_dashboard_summary_failure("2026-04-02", f"boom-{idx}")

        freshness, alerts = self.runtime_state.summarize_freshness()
        open_alerts = [alert for alert in alerts if alert.get("status") == "open"]
        self.assertTrue(
            any(alert["key"] == "dashboard-summary-failures:2026-04-02" for alert in open_alerts)
        )

    def test_crawl_status_updates_freshness(self):
        self.runtime_state.update_crawl_status("entries", success=True, details={"total_races_found": 12})
        freshness, _alerts = self.runtime_state.summarize_freshness()

        self.assertEqual(freshness["entries"]["last_details"]["total_races_found"], 12)
        self.assertFalse(freshness["entries"]["stale"])

    def test_startup_grace_suppresses_initial_stale_alerts(self):
        self.runtime_state.mark_runtime_boot("scheduler")
        freshness, _alerts = self.runtime_state.summarize_freshness()

        self.assertFalse(freshness["entries"]["stale"])
        self.assertFalse(freshness["results"]["stale"])
        self.assertFalse(freshness["scratches"]["stale"])
        self.assertTrue(freshness["entries"]["within_startup_grace"])

    def test_recent_attempt_marks_crawl_in_progress(self):
        self.runtime_state.mark_crawl_attempt("results", {"phase": "scheduled"})
        freshness, _alerts = self.runtime_state.summarize_freshness()

        self.assertTrue(freshness["results"]["in_progress"])
        self.assertFalse(freshness["results"]["stale"])

    def test_dispatches_discord_notification_once_for_open_and_resolved_alert(self):
        os.environ["ALERT_WEBHOOK_URL"] = "https://discord.example/webhook"

        with patch.object(self.runtime_state.requests, "post") as post_mock:
            post_mock.return_value.raise_for_status.return_value = None
            self.runtime_state.raise_alert("test-alert", "critical", "Test alert", {"foo": "bar"})
            self.runtime_state.raise_alert("test-alert", "critical", "Test alert", {"foo": "bar"})
            self.runtime_state.clear_alert("test-alert")

        self.assertEqual(post_mock.call_count, 2)
        first_payload = post_mock.call_args_list[0].kwargs["json"]
        second_payload = post_mock.call_args_list[1].kwargs["json"]
        self.assertIn("TrackData alert open", first_payload["content"])
        self.assertIn("TrackData alert resolved", second_payload["content"])
        self.assertEqual(second_payload["embeds"][0]["fields"][1]["value"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
