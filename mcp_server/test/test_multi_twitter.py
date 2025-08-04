import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp_server.tools.multi_twitter import MultiTwitterPlaywright
from dotenv import load_dotenv, find_dotenv

# Configure logging to show detailed information
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_multi_twitter():
    twitter = None
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize MultiTwitterPlaywright
        twitter = MultiTwitterPlaywright()
        logger.info("MultiTwitterPlaywright initialized")
        
        # Test both accounts
        accounts = ['primary', 'secondary']
        
        for account_name in accounts:
            logger.info(f"\n=== Testing {account_name} account ===")
            
            # Test login
            logger.info(f"Testing login for {account_name}...")
            login_success = await twitter.ensure_logged_in(account_name)
            if login_success:
                logger.info(f"Successfully logged in to {account_name} account")
            else:
                logger.error(f"Failed to login to {account_name} account")
                continue
            
            # Test posting a tweet
            test_tweet = f"🕵️‍♂️🖼️ #Blockchain providing irrefutable proof of ownership and provenance for AI-generated #NFTs. No more questioning the artist... even if it's a bot. #AIArtNFT #NFTAuthenticity #CryptoArt - Test from {account_name} account"
            
            logger.info(f"Attempting to post tweet with {account_name}...")
            logger.info(f"Tweet content: {test_tweet}")
            post_success = await twitter.post_tweet(test_tweet, account_name)
            if post_success:
                logger.info(f"Tweet posted successfully with {account_name} account!")
            else:
                logger.warning(f"Tweet posting failed with {account_name} account, but continuing with search and like...")
            
            # Test search and like functionality
            logger.info(f"Testing search and like functionality with {account_name}...")
            search_term = "#blockchain"
            max_likes = 2
            search_success = await twitter.search_and_like_tweets(search_term, max_likes, account_name)
            if not search_success:
                logger.error(f"Failed to search and like tweets with {account_name} account")
            else:
                logger.info(f"Search and like test completed with {account_name} account!")
            
            # Add delay between accounts
            await asyncio.sleep(5)
        
        logger.info("\n=== Multi-account Twitter test completed ===")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise
    finally:
        if twitter:
            try:
                await twitter.close_session()
                logger.info("Closed all Twitter sessions")
            except Exception as e:
                logger.error(f"Error closing sessions: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_multi_twitter()) 