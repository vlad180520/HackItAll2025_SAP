"""Test script to verify start session request."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import ExternalAPIClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_start_session():
    """Test starting a session."""
    api_key = "4d344451-01c0-49ac-91ea-d2ebef71ee0f"
    base_url = "http://localhost:8080"
    
    client = ExternalAPIClient(base_url=base_url)
    
    try:
        logger.info(f"Attempting to start session with API key: {api_key[:8]}...")
        session_id = client.start_session(api_key)
        logger.info(f"✅ Session started successfully!")
        logger.info(f"Session ID: {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"❌ Failed to start session: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    session_id = test_start_session()
    if session_id:
        print(f"\n✅ Success! Session ID: {session_id}")
    else:
        print("\n❌ Failed to start session")

