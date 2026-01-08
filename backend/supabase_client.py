"""
Supabase Client Helper Module
Provides a singleton Supabase client for database operations
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://lpimolzzjfhqfoxcdzse.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Singleton client instance
_supabase_client: Client = None


def get_supabase_client() -> Client:
    """
    Get or create the Supabase client singleton

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If SUPABASE_SERVICE_KEY is not set
    """
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_KEY environment variable is not set. "
                "Please check your .env file."
            )

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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
