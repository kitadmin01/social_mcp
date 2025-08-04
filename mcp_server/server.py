# mcp_server/server.py

import os
import logging
import asyncio
import random
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp_server.tools.extract_content import ExtractContent
from mcp_server.tools.store_tweets import StoreTweets
from mcp_server.tools.multi_twitter import MultiTwitterPlaywright
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

# Get search terms from environment
search_terms = os.getenv('SEARCH_TERMS', '#blockchain,#crypto,#web3,#defi,#nft')
SEARCH_TERMS = [term.strip() for term in search_terms.split(',')]
logger.info(f"Initialized with search terms: {SEARCH_TERMS}")

# Keep track of the last used search term index
last_search_term_index = -1

def get_next_search_term():
    """Get the next search term in rotation."""
    global last_search_term_index
    
    if not SEARCH_TERMS:
        return "#blockchain"  # fallback to default
        
    # Move to the next term in the list
    last_search_term_index = (last_search_term_index + 1) % len(SEARCH_TERMS)
    term = SEARCH_TERMS[last_search_term_index]
    logger.info(f"Selected next search term in rotation: {term}")
    return term

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
        twitter = MultiTwitterPlaywright()
        bsky = BlueskyAPI()
        scheduler = SchedulePost(sheets)
        llm = LLMOrchestrator(provider="openai")
        
        logger.info("MCP server initialization completed successfully with persistent Twitter sessions")
        
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
            logger.info("Closed Twitter sessions on server cleanup")
            
        # Cleanup any other resources
        for session in active_sessions:
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error closing session: {str(e)}")
                
        logger.info("MCP server cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

# Initialize tools
initialize_tools()

@mcp.tool()
async def extract_content(url: str) -> str:
    """Extract content from a URL."""
    return await extractor.extract(url)

@mcp.tool()
async def generate_tweets(text: str) -> list:
    """Generate tweets from content."""
    return await llm.generate_content(f"Generate 3 tweets from: {text}")

@mcp.tool()
async def store_tweets(row_id: int, tweets: list) -> str:
    """Store tweets in Google Sheets."""
    return await tweet_storer.store_tweets(row_id, tweets)

@mcp.tool()
async def post_tweet(tweet: str) -> str:
    """Post a tweet using both Twitter accounts."""
    try:
        # Post with primary account
        primary_success = await twitter.post_tweet(tweet, 'primary')
        if primary_success:
            logger.info("Tweet posted successfully with primary account")
        else:
            logger.warning("Failed to post tweet with primary account")
        
        # Post with secondary account
        secondary_success = await twitter.post_tweet(tweet, 'secondary')
        if secondary_success:
            logger.info("Tweet posted successfully with secondary account")
        else:
            logger.warning("Failed to post tweet with secondary account")
        
        if primary_success and secondary_success:
            return f"Tweet posted successfully with both accounts: {tweet[:50]}..."
        elif primary_success:
            return f"Tweet posted with primary account only: {tweet[:50]}..."
        elif secondary_success:
            return f"Tweet posted with secondary account only: {tweet[:50]}..."
        else:
            return "Failed to post tweet with both accounts"
            
    except Exception as e:
        logger.error(f"Error posting tweet: {str(e)}")
        return f"Error: {str(e)}"

@mcp.tool()
async def engage_twitter(max_likes: int = 10) -> str:
    """Engage with Twitter posts by liking them."""
    try:
        # Get search terms for each account
        search_terms_primary = os.getenv('SEARCH_TERMS_PRIMARY', '#blockchain,#crypto,#web3,#defi,#nft')
        search_terms_secondary = os.getenv('SEARCH_TERMS_SECONDARY', '#cryptotrading,#bitcoin,#ethereum,#altcoin')
        
        search_terms_primary_list = [term.strip() for term in search_terms_primary.split(',')]
        search_terms_secondary_list = [term.strip() for term in search_terms_secondary.split(',')]
        
        # Select random search terms for each account
        primary_search_term = random.choice(search_terms_primary_list)
        secondary_search_term = random.choice(search_terms_secondary_list)
        
        # Split likes between accounts
        likes_per_account = max_likes // 2
        
        # Engage with primary account using primary search terms
        logger.info(f"Primary account using search term: {primary_search_term}")
        primary_success = await twitter.search_and_like_tweets(
            search_term=primary_search_term, 
            max_likes=likes_per_account, 
            account_name='primary'
        )
        
        # Engage with secondary account using secondary search terms
        logger.info(f"Secondary account using search term: {secondary_search_term}")
        secondary_success = await twitter.search_and_like_tweets(
            search_term=secondary_search_term, 
            max_likes=likes_per_account, 
            account_name='secondary'
        )
        
        if primary_success and secondary_success:
            return f"Successfully engaged with {max_likes} tweets using both accounts"
        elif primary_success:
            return f"Primary account engaged with {likes_per_account} tweets, secondary failed"
        elif secondary_success:
            return f"Secondary account engaged with {likes_per_account} tweets, primary failed"
        else:
            return "Failed to engage with tweets using both accounts"
            
    except Exception as e:
        logger.error(f"Error engaging with Twitter: {str(e)}")
        return f"Error: {str(e)}"

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
async def engage_bsky(count: int = 5) -> str:
    """Engage with posts on Bluesky."""
    try:
        search_term = get_next_search_term()
        logger.info(f"Engaging with {count} posts on Bluesky using term: {search_term}")
        await bsky.search_and_like_blockchain(search_term=search_term, like_count=count)
        return f"Engaged with {count} posts on Bluesky using term: {search_term}"
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