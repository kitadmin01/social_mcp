import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp_server.tools.linkedin import LinkedInAPI
from dotenv import load_dotenv, find_dotenv

# Configure logging to show detailed information
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_linkedin():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path)
        
        # Initialize LinkedInAPI
        linkedin = LinkedInAPI()
        logger.info("LinkedInAPI initialized")
        
        # Test parameters
        like_count = 12  # Number of posts to like
        search_query = "#blockchain"
        logger.info(f"Will attempt to like {like_count} posts with query: {search_query}")
        
        # Attempt to search and like posts
        logger.info("Starting post search and like...")
        results = linkedin.search_and_like_posts(query=search_query, like_count=like_count)
        
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
        asyncio.run(test_linkedin())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}") 