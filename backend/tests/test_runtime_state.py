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

    def test_resolved_payload_omits_empty_detail_values(self):
        payload = self.runtime_state._build_alert_payload(  # pylint: disable=protected-access
            {
                "key": "crawl-stale:entries",
                "severity": "warning",
                "message": "Entries crawl is stale",
                "status": "resolved",
                "count": 2,
                "details": {
                    "last_success_at": "2026-04-02T22:46:41Z",
                    "age_minutes": 0,
                    "stale": False,
                    "last_attempt_at": None,
                    "last_error": None,
                },
            }
        )

        self.assertIn("TrackData alert resolved", payload["content"])
        self.assertEqual(payload["embeds"][0]["title"], "Entries crawl is stale")
        description = payload["embeds"][0]["description"]
        self.assertIn("**Last Success:** 2026-04-02T22:46:41Z", description)
        self.assertIn("**Age (minutes):** 0", description)
        self.assertNotIn("last_attempt_at", description)
        self.assertNotIn("last_error", description)
        self.assertNotIn("stale", description)
        self.assertNotIn("count", description)

    def test_payload_flattens_last_details_and_omits_false_flags(self):
        payload = self.runtime_state._build_alert_payload(  # pylint: disable=protected-access
            {
                "key": "crawl-stale:scratches",
                "severity": "critical",
                "message": "Scratches crawl is stale",
                "status": "open",
                "details": {
                    "last_success_at": None,
                    "last_attempt_at": "2026-04-03T01:47:39Z",
                    "in_progress": False,
                    "within_startup_grace": False,
                    "stale": True,
                    "last_details": {
                        "phase": "startup",
                        "target_date": "2026-04-02",
                        "changes_processed": 3,
                    },
                },
            }
        )

        description = payload["embeds"][0]["description"]
        self.assertIn("**Phase:** startup", description)
        self.assertIn("**Target Date:** 2026-04-02", description)
        self.assertIn("**Changes Processed:** 3", description)
        self.assertNotIn("last_details", description)
        self.assertNotIn("in_progress", description)
        self.assertNotIn("within_startup_grace", description)
        self.assertNotIn("stale", description)
        self.assertNotIn("count", description)

    def test_startup_grace_resolution_does_not_dispatch_noise(self):
        os.environ["ALERT_WEBHOOK_URL"] = "https://discord.example/webhook"

        with patch.object(self.runtime_state.requests, "post") as post_mock:
            post_mock.return_value.raise_for_status.return_value = None
            self.runtime_state.raise_alert(
                "crawl-stale:results",
                "critical",
                "Results crawl is stale",
                {"stale": True, "threshold_minutes": 30},
            )
            self.runtime_state.mark_runtime_boot("scheduler")
            self.runtime_state.evaluate_runtime_alerts()

        self.assertEqual(post_mock.call_count, 1)
        first_payload = post_mock.call_args_list[0].kwargs["json"]
        self.assertIn("TrackData alert open", first_payload["content"])

    def test_dashboard_alert_evaluation_does_not_open_crawl_stale_alerts(self):
        self.runtime_state.evaluate_runtime_alerts(
            today_summary_total=5,
            during_racing_hours=True,
            include_crawl_alerts=False,
        )

        _freshness, alerts = self.runtime_state.summarize_freshness()
        open_alerts = [alert for alert in alerts if alert.get("status") == "open"]
        self.assertEqual(open_alerts, [])


if __name__ == "__main__":
    unittest.main()
