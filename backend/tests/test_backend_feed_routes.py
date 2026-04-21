import os
import sys
import subprocess
import tempfile
import types
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend import backend as backend_module


class FakeSupabaseQuery:
    def __init__(self, client):
        self.client = client
        self.action = None
        self.table_name = client.table_name

    def insert(self, payload):
        self.action = "insert"
        self.client.insert_payload = payload
        return self

    def select(self, *args):
        self.action = "select"
        return self

    def update(self, payload):
        self.action = "update"
        self.client.update_payload = payload
        self.client.update_payloads.append(payload)
        return self

    def delete(self):
        self.action = "delete"
        self.client.delete_called = True
        return self

    def eq(self, *args):
        self.client.eq_args = args
        self.client.eq_args_list.append(args)
        return self

    def limit(self, *args):
        return self

    def execute(self):
        if self.action == "insert":
            return types.SimpleNamespace(data=[{"id": "upload-log-id"}])
        if self.action == "select":
            return types.SimpleNamespace(data=self.client.select_data.pop(0) if self.client.select_data else [])
        return types.SimpleNamespace(data=[])


class FakeSupabaseClient:
    def __init__(self):
        self.table_name = None
        self.insert_payload = None
        self.update_payload = None
        self.update_payloads = []
        self.eq_args = None
        self.eq_args_list = []
        self.select_data = []
        self.delete_called = False

    def table(self, table_name):
        self.table_name = table_name
        return FakeSupabaseQuery(self)


class TestBackendFeedRoutes(unittest.TestCase):
    def setUp(self):
        self.client = backend_module.app.test_client()

    def test_upload_drf_queues_background_parse(self):
        fake_supabase = FakeSupabaseClient()

        with tempfile.TemporaryDirectory() as upload_dir, patch.dict(backend_module.app.config, {"UPLOAD_FOLDER": upload_dir}), patch.object(
            backend_module, "get_supabase_client", return_value=fake_supabase
        ), patch.object(
            backend_module, "submit_drf_parse_job"
        ) as submit_job:
            response = self.client.post(
                "/api/upload-drf",
                data={"file": (BytesIO(b"%PDF-1.4"), "queued.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(fake_supabase.insert_payload["upload_status"], "queued")
        self.assertEqual(fake_supabase.insert_payload["parse_status"], "queued")
        self.assertEqual(fake_supabase.insert_payload["file_path"], "queued.pdf")
        submit_job.assert_called_once_with("upload-log-id", "queued.pdf")

    def test_run_drf_parse_job_timeout_marks_upload_log_failed(self):
        fake_supabase = FakeSupabaseClient()

        with tempfile.TemporaryDirectory() as upload_dir:
            with open(os.path.join(upload_dir, "timeout.pdf"), "wb") as pdf_file:
                pdf_file.write(b"%PDF-1.4")

            with patch.dict(backend_module.app.config, {"UPLOAD_FOLDER": upload_dir}), patch.object(
                backend_module, "get_supabase_client", return_value=fake_supabase
            ), patch.object(
                backend_module.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd=["python", "parse_drf.py"], timeout=backend_module.DRF_PARSE_TIMEOUT_SECONDS),
            ):
                backend_module.run_drf_parse_job("upload-log-id", "timeout.pdf")

        self.assertEqual(fake_supabase.update_payload["upload_status"], "failed")
        self.assertEqual(fake_supabase.update_payload["parse_status"], "failed")
        self.assertIn("timed out", fake_supabase.update_payload["error_message"])

    def test_delete_upload_removes_log_and_unreferenced_local_file(self):
        fake_supabase = FakeSupabaseClient()
        fake_supabase.select_data = [
            [{"id": "upload-log-id", "filename": "remove.pdf", "file_path": "remove.pdf"}],
            [],
        ]

        with tempfile.TemporaryDirectory() as upload_dir:
            upload_path = os.path.join(upload_dir, "remove.pdf")
            with open(upload_path, "wb") as pdf_file:
                pdf_file.write(b"%PDF-1.4")

            with patch.dict(backend_module.app.config, {"UPLOAD_FOLDER": upload_dir}), patch.object(
                backend_module, "get_supabase_client", return_value=fake_supabase
            ):
                response = self.client.delete("/api/uploads/upload-log-id")

            self.assertEqual(response.status_code, 200)
            self.assertTrue(fake_supabase.delete_called)
            self.assertFalse(os.path.exists(upload_path))

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
