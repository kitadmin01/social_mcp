# mcp_server/server.py

import os
import logging
import asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp_server.tools.extract_content import ExtractContent
from mcp_server.tools.store_tweets import StoreTweets
from mcp_server.tools.post_tweets import TwitterPlaywright
from mcp_server.tools.bsky import BlueskyAPI
from mcp_server.tools.schedule_post import SchedulePost
from common.google_sheets import GoogleSheetsClient
from common.llm_orchestrator import LLMOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global state for cleanup
active_sessions = set()

# Initialize MCP server
mcp = FastMCP("SocialMCP")
logger.info("Initialized FastMCP instance")

# Initialize tools
def initialize_tools():
    """Initialize all tools and resources."""
    try:
        logger.info("Starting MCP server initialization...")
        
        # Initialize Google Sheets client
        GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
        if not GOOGLE_SHEET_ID:
            raise ValueError("GOOGLE_SHEET_ID environment variable is not set")
            
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "google_sheets_credentials.json")
        logger.info(f"Using Google Sheet ID: {GOOGLE_SHEET_ID}")
        logger.info(f"Using credentials file: {credentials_path}")
        
        # Initialize all tools
        global sheets, extractor, tweet_storer, twitter, bsky, scheduler, llm
        sheets = GoogleSheetsClient(credentials_path, GOOGLE_SHEET_ID)
        extractor = ExtractContent()
        tweet_storer = StoreTweets(sheets)
        twitter = TwitterPlaywright()
        bsky = BlueskyAPI()
        scheduler = SchedulePost(sheets)
        llm = LLMOrchestrator(provider="openai")
        
        logger.info("MCP server initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during MCP server initialization: {str(e)}")
        raise

async def cleanup_resources():
    """Cleanup all resources."""
    try:
        logger.info("Starting MCP server cleanup...")
        
        # Cleanup Twitter session
        if hasattr(twitter, 'close_session'):
            await twitter.close_session()
            
        # Cleanup any other resources
        for session in active_sessions:
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error closing session: {str(e)}")
                
        logger.info("MCP server cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during MCP server cleanup: {str(e)}")

@mcp.tool()
async def extract_content(url: str) -> str:
    """Extract content from a URL."""
    try:
        logger.info(f"Extracting content from URL: {url}")
        return await extractor.extract(url)
    except Exception as e:
        logger.error(f"Error extracting content: {str(e)}")
        raise

@mcp.tool()
async def generate_tweets(text: str) -> list:
    """Generate tweets from text content."""
    try:
        logger.info(f"Generating tweets for text: {text[:50]}...")
        return await llm.generate_content(f"Generate 6 tweets for: {text}")
    except Exception as e:
        logger.error(f"Error generating tweets: {str(e)}")
        raise

@mcp.tool()
async def store_tweets(row_id: int, tweets: list) -> str:
    """Store generated tweets."""
    try:
        logger.info(f"Storing tweets for row {row_id}")
        await tweet_storer.store_llm_tweets(row_id, tweets)
        return "stored"
    except Exception as e:
        logger.error(f"Error storing tweets: {str(e)}")
        raise

@mcp.tool()
async def post_tweet(tweet: str) -> str:
    """Post a tweet to Twitter."""
    try:
        logger.info(f"Posting tweet: {tweet[:50]}...")
        await twitter.post_tweet(tweet)
        return "tweeted"
    except Exception as e:
        logger.error(f"Error posting tweet: {str(e)}")
        raise

@mcp.tool()
async def post_bsky(text: str) -> str:
    """Post content to Bluesky."""
    try:
        logger.info(f"Posting to Bluesky: {text[:50]}...")
        await bsky.create_post(text)
        return "posted to bsky"
    except Exception as e:
        logger.error(f"Error posting to Bluesky: {str(e)}")
        raise

@mcp.tool()
async def engage_twitter(count: int = 5) -> str:
    """Engage with tweets on Twitter."""
    try:
        logger.info(f"Engaging with {count} tweets on Twitter")
        await twitter.like_blockchain_tweets(min_likes=count, max_likes=count)
        return f"Engaged with {count} tweets on Twitter"
    except Exception as e:
        logger.error(f"Error engaging with Twitter: {str(e)}")
        raise

@mcp.tool()
async def engage_bsky(count: int = 5) -> str:
    """Engage with posts on Bluesky."""
    try:
        logger.info(f"Engaging with {count} posts on Bluesky")
        await bsky.search_and_like_blockchain(like_count=count)
        return f"Engaged with {count} posts on Bluesky"
    except Exception as e:
        logger.error(f"Error engaging with Bluesky: {str(e)}")
        raise

@mcp.tool()
async def schedule_post(row_id: int, tweet: str) -> str:
    """Schedule a post for later."""
    try:
        logger.info(f"Scheduling post for row {row_id}")
        await scheduler.wait_and_post(row_id, twitter.post_tweet, tweet)
        return "scheduled"
    except Exception as e:
        logger.error(f"Error scheduling post: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting MCP server...")
        # Initialize tools before starting the server
        initialize_tools()
        
        # Set up cleanup handler
        import atexit
        atexit.register(lambda: asyncio.run(cleanup_resources()))
        
        # Start the server
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Error running MCP server: {str(e)}")
        raise