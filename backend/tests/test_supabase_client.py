import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx


class SupabaseClientConfigTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_KEY": "service-key",
            "SUPABASE_POSTGREST_TIMEOUT_SECONDS": "12",
        },
        clear=False,
    )
    def test_client_uses_configured_postgrest_timeout(self):
        import backend.supabase_client as supabase_client

        class FakeOptions:
            def __init__(self, postgrest_client_timeout, **kwargs):
                self.postgrest_client_timeout = postgrest_client_timeout
                self.httpx_client = kwargs.get("httpx_client")

        with patch("supabase.create_client") as create_client:
            importlib.reload(supabase_client)
            supabase_client._supabase_client = None
            supabase_client.SyncClientOptions = FakeOptions

            supabase_client.get_supabase_client()

            _, _, kwargs = create_client.mock_calls[0]
            options = kwargs["options"]
            self.assertEqual(options.postgrest_client_timeout, 12.0)

    @patch.dict(
        os.environ,
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_KEY": "service-key",
            "SUPABASE_CLIENT_MAX_AGE_SECONDS": "60",
        },
        clear=False,
    )
    def test_client_refreshes_after_max_age(self):
        import backend.supabase_client as supabase_client

        first_client = SimpleNamespace(postgrest=SimpleNamespace(aclose=lambda: None))
        second_client = SimpleNamespace(postgrest=SimpleNamespace(aclose=lambda: None))

        with patch("supabase.create_client", side_effect=[first_client, second_client]) as create_client:
            importlib.reload(supabase_client)
            supabase_client._supabase_client = None
            supabase_client._supabase_client_created_at = 0.0
            supabase_client.SyncClientOptions = None

            with patch.object(supabase_client.time, "time", side_effect=[100.0, 200.0, 200.0]):
                client_a = supabase_client.get_supabase_client()
                client_b = supabase_client.get_supabase_client()

            self.assertIs(client_a, first_client)
            self.assertIs(client_b, second_client)
            self.assertEqual(create_client.call_count, 2)

    @patch.dict(
        os.environ,
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_KEY": "service-key",
            "SUPABASE_QUERY_RETRY_ATTEMPTS": "1",
        },
        clear=False,
    )
    def test_table_queries_retry_once_on_timeout_with_fresh_client(self):
        import backend.supabase_client as supabase_client

        class FakeBuilder:
            def __init__(self, outcome):
                self.outcome = outcome

            def select(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                if isinstance(self.outcome, Exception):
                    raise self.outcome
                return self.outcome

        class FakeClient:
            def __init__(self, outcome):
                self.outcome = outcome
                self.postgrest = SimpleNamespace(aclose=lambda: None)

            def table(self, _name):
                return FakeBuilder(self.outcome)

        timeout_exc = httpx.ReadTimeout("timed out")
        first_client = FakeClient(timeout_exc)
        second_client = FakeClient(SimpleNamespace(data=[{"id": 1}]))

        with patch("supabase.create_client", side_effect=[first_client, second_client]) as create_client:
            importlib.reload(supabase_client)
            supabase_client._supabase_client = None
            supabase_client._supabase_client_created_at = 0.0

            client = supabase_client.get_supabase_client()
            response = client.table("hranalyzer_tracks").select("id").limit(1).execute()

            self.assertEqual(response.data, [{"id": 1}])
            self.assertEqual(create_client.call_count, 2)


if __name__ == "__main__":
    unittest.main()
