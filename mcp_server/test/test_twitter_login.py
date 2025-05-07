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
    twitter = None
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize TwitterPlaywright
        twitter = TwitterPlaywright()
        logger.info("TwitterPlaywright initialized")
        
        # Test tweet content
        test_tweet = """🕵️‍♂️🖼️ #Blockchain providing irrefutable proof of ownership and provenance for AI-generated #NFTs. No more questioning the artist... even if it's a bot. #AIArtNFT #NFTAuthenticity #CryptoArt"""
        
        # Attempt to post tweet
        logger.info("Attempting to post tweet...")
        logger.info(f"Tweet content: {test_tweet}")
        post_success = await twitter.post_tweet(test_tweet)
        if post_success:
            logger.info("Tweet posted successfully!")
        else:
            logger.warning("Tweet posting failed, but continuing with search and like...")
        
        # Test search and like functionality
        logger.info("Testing search and like functionality...")
        search_term = "#blockchain"
        max_likes = 3
        search_success = await twitter.search_and_like_tweets(search_term, max_likes)
        if not search_success:
            raise Exception("Failed to search and like tweets")
        logger.info("Search and like test completed!")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise
    finally:
        if twitter:
            try:
                await twitter.close_session()
            except:
                pass

if __name__ == "__main__":
    try:
        # Run the test
        asyncio.run(test_twitter_login())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)  # Exit with error code 