
import os
import time
import sys
import logging
import tempfile
from datetime import datetime

# Configuration
HEARTBEAT_FILE = os.path.join(tempfile.gettempdir(), "crawler_heartbeat")
THRESHOLD_SECONDS = 1200 # 20 minutes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HealthCheck")

def check_heartbeat():
    if not os.path.exists(HEARTBEAT_FILE):
        logger.error(f"Heartbeat file not found at {HEARTBEAT_FILE}")
        return False
        
    mtime = os.path.getmtime(HEARTBEAT_FILE)
    age = time.time() - mtime
    
    if age > THRESHOLD_SECONDS:
        logger.error(f"Heartbeat is stale! Age: {age:.0f}s (Threshold: {THRESHOLD_SECONDS}s)")
        return False
        
    logger.info(f"Heartbeat is healthy. Age: {age:.1f}s")
    return True

if __name__ == "__main__":
    if check_heartbeat():
        sys.exit(0)
    else:
        sys.exit(1)
