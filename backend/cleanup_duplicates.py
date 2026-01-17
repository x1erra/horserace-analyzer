
import os
import sys
import logging
from supabase_client import get_supabase_client

# Ensure we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cleanup")

def cleanup():
    sb = get_supabase_client()
    
    # Delete 'Scratch' type changes where entry_id is NULL
    # This removes the "Race-wide" scratches which are parsing errors
    logger.info("Cleaning up Race-wide scratches...")
    
    # Supabase syntax: delete().eq(col, val).is_(col, val)
    # Using 'is' for null check
    try:
        res = sb.table('hranalyzer_changes') \
            .delete() \
            .eq('change_type', 'Scratch') \
            .is_('entry_id', 'null') \
            .execute()
            
        logger.info(f"Deleted {len(res.data)} bad records.")
    except Exception as e:
        logger.error(f"Error cleaning up: {e}")

if __name__ == "__main__":
    cleanup()
