import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp_server.tools.post_tweets import TwitterPlaywright
from dotenv import load_dotenv, find_dotenv

# Configure logging to show detailed information
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_like_tweets():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize TwitterPlaywright
        twitter = TwitterPlaywright()
        logger.info("TwitterPlaywright initialized")
        
        # Test parameters
        min_likes = 5
        max_likes = 10
        logger.info(f"Will attempt to like between {min_likes} and {max_likes} tweets")
        
        # Attempt to like tweets
        logger.info("Starting to like blockchain tweets...")
        await twitter.like_blockchain_tweets(min_likes=min_likes, max_likes=max_likes)
        logger.info("Tweet liking completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run the test
        asyncio.run(test_like_tweets())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 