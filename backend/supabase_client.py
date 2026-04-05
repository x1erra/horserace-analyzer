"""
Supabase Client Helper Module
Provides a singleton Supabase client for database operations
"""

import os
import time
import httpx
from supabase import create_client, Client
from dotenv import load_dotenv

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
SUPABASE_CLIENT_MAX_AGE_SECONDS = float(os.getenv('SUPABASE_CLIENT_MAX_AGE_SECONDS', '60'))

# Singleton client instance
_supabase_client: Client = None
_supabase_client_created_at: float = 0.0


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
        httpx_client = httpx.Client(
            timeout=httpx.Timeout(SUPABASE_POSTGREST_TIMEOUT_SECONDS),
            follow_redirects=True,
            http2=False,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=0,
                keepalive_expiry=0,
            ),
        )
        client_kwargs["options"] = SyncClientOptions(
            postgrest_client_timeout=SUPABASE_POSTGREST_TIMEOUT_SECONDS,
            httpx_client=httpx_client,
        )

    return client_kwargs


def get_supabase_client(force_refresh: bool = False) -> Client:
    """
    Get or create the Supabase client singleton

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If SUPABASE_SERVICE_KEY is not set
    """
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
