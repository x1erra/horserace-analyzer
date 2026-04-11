"""
Supabase Client Helper Module
Provides a singleton Supabase client for database operations
"""

import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client

try:
    from supabase.lib.client_options import SyncClientOptions
except Exception:  # pragma: no cover - test stubs may not expose submodules
    SyncClientOptions = None

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://vytyhtddhplcrvvgidyy.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SERVICE_ROLE')
SUPABASE_POSTGREST_TIMEOUT_SECONDS = float(os.getenv('SUPABASE_POSTGREST_TIMEOUT_SECONDS', '15'))
SUPABASE_CLIENT_MAX_AGE_SECONDS = float(os.getenv('SUPABASE_CLIENT_MAX_AGE_SECONDS', '14400'))
SUPABASE_QUERY_RETRY_ATTEMPTS = max(int(os.getenv('SUPABASE_QUERY_RETRY_ATTEMPTS', '1')), 0)
SUPABASE_HTTPX_MAX_CONNECTIONS = max(int(os.getenv('SUPABASE_HTTPX_MAX_CONNECTIONS', '6')), 1)
SUPABASE_HTTPX_MAX_KEEPALIVE_CONNECTIONS = max(
    int(os.getenv('SUPABASE_HTTPX_MAX_KEEPALIVE_CONNECTIONS', '4')),
    0,
)
SUPABASE_HTTPX_KEEPALIVE_EXPIRY_SECONDS = float(
    os.getenv('SUPABASE_HTTPX_KEEPALIVE_EXPIRY_SECONDS', '15')
)

# Singleton client instance
_supabase_client: Client = None
_supabase_client_created_at: float = 0.0


def _is_retryable_database_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True

    message = str(exc).lower()
    retry_markers = (
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "temporarily unavailable",
        "server disconnected",
        "remote protocol error",
    )
    return any(marker in message for marker in retry_markers)


def _build_httpx_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(SUPABASE_POSTGREST_TIMEOUT_SECONDS),
        follow_redirects=True,
        http2=False,
        trust_env=False,
        limits=httpx.Limits(
            max_connections=SUPABASE_HTTPX_MAX_CONNECTIONS,
            max_keepalive_connections=SUPABASE_HTTPX_MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=SUPABASE_HTTPX_KEEPALIVE_EXPIRY_SECONDS,
        ),
    )


class ResilientTableQuery:
    """Replay a PostgREST query chain on a fresh client when transient reads fail."""

    def __init__(self, table_name: str):
        self._table_name = table_name
        self._operations: list[tuple[str, str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, item):
        if item == "not_":
            self._operations.append(("attr", item, (), {}))
            return self

        def recorder(*args, **kwargs):
            self._operations.append(("call", item, args, kwargs))
            return self

        return recorder

    def _materialize(self, force_refresh: bool = False):
        client = _get_raw_supabase_client(force_refresh=force_refresh)
        raw_table = getattr(client, "_trackdata_raw_table", client.table)
        builder = raw_table(self._table_name)
        for kind, name, args, kwargs in self._operations:
            if kind == "attr":
                builder = getattr(builder, name)
            else:
                result = getattr(builder, name)(*args, **kwargs)
                if result is not None:
                    builder = result
        return builder

    def execute(self):
        attempts = SUPABASE_QUERY_RETRY_ATTEMPTS + 1
        last_error = None

        for attempt_index in range(attempts):
            try:
                builder = self._materialize(force_refresh=attempt_index > 0)
                return builder.execute()
            except Exception as exc:  # pragma: no cover - exercised through callers
                last_error = exc
                if attempt_index >= attempts - 1 or not _is_retryable_database_error(exc):
                    raise
                reset_supabase_client()

        raise last_error


def _close_client(client: Client) -> None:
    try:
        client.postgrest.aclose()
    except Exception:
        pass


def reset_supabase_client() -> None:
    global _supabase_client, _supabase_client_created_at

    if _supabase_client is not None:
        _close_client(_supabase_client)
    _supabase_client = None
    _supabase_client_created_at = 0.0


def _build_client_kwargs():
    client_kwargs = {}

    if SyncClientOptions is not None:
        httpx_client = _build_httpx_client()
        client_kwargs["options"] = SyncClientOptions(
            postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_SECONDS,
            httpx_client=httpx_client,
        )

    return client_kwargs


def _patch_client(client: Client) -> Client:
    if getattr(client, "_trackdata_resilient_client", False):
        return client

    if not hasattr(client, "table"):
        return client

    raw_table = client.table

    def resilient_table(table_name: str):
        return ResilientTableQuery(table_name)

    client._trackdata_raw_table = raw_table
    client.table = resilient_table
    client._trackdata_resilient_client = True
    return client


def _get_raw_supabase_client(force_refresh: bool = False) -> Client:
    global _supabase_client, _supabase_client_created_at

    should_refresh = force_refresh
    if _supabase_client is not None and SUPABASE_CLIENT_MAX_AGE_SECONDS > 0:
        should_refresh = should_refresh or (
            (time.time() - _supabase_client_created_at) >= SUPABASE_CLIENT_MAX_AGE_SECONDS
        )

    if should_refresh:
        reset_supabase_client()

    if _supabase_client is None:
        if not SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_KEY (or SUPABASE_SERVICE_ROLE) environment variable is not set. "
                "Please check your .env file."
            )

        client_kwargs = _build_client_kwargs()
        _supabase_client = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_KEY,
            **client_kwargs,
        )
        _supabase_client_created_at = time.time()

    return _supabase_client


def get_supabase_client(force_refresh: bool = False) -> Client:
    """
    Get or create the Supabase client singleton

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If SUPABASE_SERVICE_KEY is not set
    """
    return _patch_client(_get_raw_supabase_client(force_refresh=force_refresh))


def test_connection():
    """
    Test the Supabase connection by querying the tracks table

    Returns:
        dict: Connection test result with status and data
    """
    try:
        client = get_supabase_client()

        # Query the tracks table to verify connection
        response = client.table('hranalyzer_tracks').select('track_code, track_name').limit(5).execute()

        return {
            'status': 'success',
            'message': 'Successfully connected to Supabase',
            'tracks_count': len(response.data),
            'sample_tracks': response.data
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to connect to Supabase: {str(e)}'
        }


if __name__ == '__main__':
    # Test connection when running this file directly
    print("Testing Supabase connection...")
    result = test_connection()

    if result['status'] == 'success':
        print(f"✓ {result['message']}")
        print(f"✓ Found {result['tracks_count']} tracks in database")
        print("\nSample tracks:")
        for track in result['sample_tracks']:
            print(f"  - {track['track_code']}: {track['track_name']}")
    else:
        print(f"✗ {result['message']}")
