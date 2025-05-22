import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp_server.tools.linkedin import LinkedInPoster
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
        
        # Initialize LinkedInPoster
        linkedin = LinkedInPoster()
        logger.info("LinkedInPoster initialized")
        
        # Test URL
        test_url = "https://analytickit.com/future-of-affiliate-marketing-in-the-decentralized-web/"
        logger.info(f"Testing with URL: {test_url}")
        
        # Generate content
        logger.info("Generating LinkedIn post content...")
        content = await linkedin.generate_linkedin_content(test_url)
        logger.info(f"Generated content: {content}")
        
        # Post to LinkedIn
        logger.info("Posting to LinkedIn...")
        success = linkedin.post_to_linkedin(content, test_url)
        
        if success:
            logger.info("Successfully posted to LinkedIn")
        else:
            logger.error("Failed to post to LinkedIn")
        
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