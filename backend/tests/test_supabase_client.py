import importlib
import os
import unittest
from unittest.mock import patch


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
            def __init__(self, postgrest_client_timeout):
                self.postgrest_client_timeout = postgrest_client_timeout

        with patch("supabase.create_client") as create_client:
            importlib.reload(supabase_client)
            supabase_client._supabase_client = None
            supabase_client.SyncClientOptions = FakeOptions

            supabase_client.get_supabase_client()

            _, _, kwargs = create_client.mock_calls[0]
            options = kwargs["options"]
            self.assertEqual(options.postgrest_client_timeout, 12.0)


if __name__ == "__main__":
    unittest.main()
