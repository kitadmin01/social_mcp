import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp_server.tools.bsky import BlueskyAPI
from dotenv import load_dotenv, find_dotenv

# Configure logging to show detailed information
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_bsky_post():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize BlueskyAPI
        bsky = BlueskyAPI()
        logger.info("BlueskyAPI initialized")
        
        # Test post content
        test_post = """🚨 Don't get REKT! Prioritizing security in #blockchain and #crypto is non-negotiable. Stay vigilant! #Web3SafetyTips #CryptoSecurityAlert"""
        
        # Attempt to post
        logger.info("Attempting to post to Bluesky...")
        logger.info(f"Post content: {test_post}")
        result = bsky.create_post(test_post)
        logger.info(f"Post created successfully! Response: {result}")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run the test
        asyncio.run(test_bsky_post())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 