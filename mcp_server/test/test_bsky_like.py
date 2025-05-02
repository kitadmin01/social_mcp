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

async def test_bsky_like():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize BlueskyAPI
        bsky = BlueskyAPI()
        logger.info("BlueskyAPI initialized")
        
        # Test parameters
        like_count = 3  # Number of posts to like
        logger.info(f"Will attempt to like {like_count} blockchain posts")
        
        # Attempt to search and like posts
        logger.info("Starting blockchain post search and like...")
        results = bsky.search_and_like_blockchain(like_count=like_count)
        
        # Log results
        logger.info(f"Successfully liked {len(results)} posts")
        for i, result in enumerate(results, 1):
            logger.info(f"Like {i} result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run the test
        asyncio.run(test_bsky_like())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 