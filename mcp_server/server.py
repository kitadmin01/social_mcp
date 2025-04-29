# mcp_server/server.py

import os
import logging
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
logger.info(f"Using Google Sheet ID: {GOOGLE_SHEET_ID}")

# Get the absolute path to the credentials file
credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "google_sheets_credentials.json")
logger.info(f"Using credentials file: {credentials_path}")

sheets = GoogleSheetsClient(credentials_path, GOOGLE_SHEET_ID)
extractor = ExtractContent()
tweet_storer = StoreTweets(sheets)
twitter = TwitterPlaywright()
bsky = BlueskyAPI()
scheduler = SchedulePost(sheets)
llm = LLMOrchestrator(provider="openai")

mcp = FastMCP("SocialMCP")
logger.info("Initialized FastMCP instance")

@mcp.tool()
async def extract_content(url: str) -> str:
    logger.info(f"Extracting content from URL: {url}")
    return await extractor.extract(url)

@mcp.tool()
def generate_tweets(text: str) -> list:
    logger.info(f"Generating tweets for text: {text[:50]}...")
    return llm.generate_content(f"Generate 6 tweets for: {text}")

@mcp.tool()
def store_tweets(row_id: int, tweets: list) -> str:
    logger.info(f"Storing tweets for row {row_id}")
    tweet_storer.store_llm_tweets(row_id, tweets)
    return "stored"

@mcp.tool()
def post_tweet(tweet: str) -> str:
    logger.info(f"Posting tweet: {tweet[:50]}...")
    twitter.post_tweet(tweet)
    return "tweeted"

@mcp.tool()
def post_bsky(text: str) -> str:
    logger.info(f"Posting to Bluesky: {text[:50]}...")
    bsky.create_post(text)
    return "posted to bsky"

@mcp.tool()
def engage_twitter(count: int = 5) -> str:
    logger.info(f"Engaging with {count} tweets on Twitter")
    twitter.like_blockchain_tweets(like_count=count)
    return f"Engaged with {count} tweets on Twitter"

@mcp.tool()
def engage_bsky(count: int = 5) -> str:
    logger.info(f"Engaging with {count} posts on Bluesky")
    bsky.search_and_like_blockchain(like_count=count)
    return f"Engaged with {count} posts on Bluesky"

@mcp.tool()
def schedule_post(row_id: int, tweet: str) -> str:
    logger.info(f"Scheduling post for row {row_id}")
    scheduler.wait_and_post(row_id, twitter.post_tweet, tweet)
    return "scheduled"

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    mcp.run(transport="stdio")  # or "sse" for server-sent events