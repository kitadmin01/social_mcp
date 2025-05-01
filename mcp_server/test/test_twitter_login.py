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

async def test_twitter_login():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize TwitterPlaywright
        twitter = TwitterPlaywright()
        logger.info("TwitterPlaywright initialized")
        
        # Test tweet content
        test_tweet = """Imagine decentralized autonomous organizations (DAOs) for specific creative niches, managed by agentic #blockchain and funded by #crypto, directly commissioning and supporting artists in #web3. 🎨🔗💰 #ArtDAOs #CryptoSupport"""
        
        # Attempt to post tweet
        logger.info("Attempting to post tweet...")
        logger.info(f"Tweet content: {test_tweet}")
        await twitter.post_tweet(test_tweet)
        logger.info("Tweet posted successfully!")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run the test
        asyncio.run(test_twitter_login())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 