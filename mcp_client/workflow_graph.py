# Placeholder for LangGraph workflow definition
# Define nodes for each tool and edges for control flow and retries

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from datetime import datetime
import time
import random
from urllib.parse import urlparse
import os
import logging
from dotenv import load_dotenv
import json

from common.google_sheets import GoogleSheetsClient
from common.llm_orchestrator import LLMOrchestrator
from common.retry_utils import retry_with_backoff
from mcp_server.tools.extract_content import ExtractContent
from mcp_server.tools.store_tweets import StoreTweets
from mcp_server.tools.post_tweets import TwitterPlaywright
from mcp_server.tools.bsky import BlueskyAPI
from mcp_server.tools.schedule_post import SchedulePost

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class WorkflowGraph:
    def __init__(self, batch_size=5, engage_count=7):
        self.M = batch_size
        self.HASHTAG = "#blockchain"
        self.ENGAGE_COUNT = engage_count
        
        # Get credentials path and sheet ID from environment
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "google_sheets_credentials.json")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        
        if not sheet_id:
            raise ValueError("GOOGLE_SHEET_ID environment variable is not set")
            
        logger.info(f"Initializing GoogleSheetsClient with sheet ID: {sheet_id}")
        self.sheets = GoogleSheetsClient(credentials_path, sheet_id)
        self.llm = LLMOrchestrator(provider="openai")
        self.extractor = ExtractContent()
        self.tweet_storer = StoreTweets(self.sheets)
        self.twitter = TwitterPlaywright()
        self.bsky = BlueskyAPI()
        self.scheduler = SchedulePost(self.sheets)

    def now(self):
        return datetime.utcnow().isoformat()

    def is_valid_url(self, url):
        if not isinstance(url, str):
            logger.warning(f"URL is not a string: {url}")
            return False
        if url.lower() in ['pending', 'in_progress', 'complete', 'error']:
            logger.warning(f"URL is a status value: {url}")
            return False
        try:
            result = urlparse(url)
            is_valid = all([result.scheme, result.netloc])
            if not is_valid:
                logger.warning(f"Invalid URL format: {url}")
            return is_valid
        except Exception as e:
            logger.warning(f"URL parsing error for {url}: {str(e)}")
            return False

    def batch_retrieval(self, state):
        try:
            logger.info("Retrieving pending URLs from Google Sheet")
            rows = self.sheets.get_pending_urls()[:self.M]
            logger.info(f"Found {len(rows)} pending rows")
            
            valid_rows = []
            for row in rows:
                url = row.get('url', '')
                logger.info(f"Processing row {row.get('id')} with URL: {url}")
                
                if self.is_valid_url(url):
                    logger.info(f"Valid URL found: {url}")
                    self.sheets.update_row(row['id'], {"status": "in_progress", "processing_ts": self.now()})
                    valid_rows.append(row)
                else:
                    logger.warning(f"Invalid URL in row {row.get('id')}: {url}")
                    self.sheets.update_row(row['id'], {
                        "status": "error",
                        "processing_ts": self.now(),
                        "retry_count_content": 0,
                        "content_ts": self.now()
                    })
            
            logger.info(f"Returning {len(valid_rows)} valid rows for processing")
            return {"rows": valid_rows, "current_row": None, "text": None, "tweets": None}
        except Exception as e:
            logger.error(f"Error in batch_retrieval: {str(e)}")
            return {"error": str(e)}

    async def extract_content_node(self, state):
        if not state.get('rows'):
            logger.info("No rows to process")
            return state
            
        # Get the first row to process
        row = state['rows'][0]
        url = row.get('url', '')
        logger.info(f"Extracting content from URL: {url}")
        
        async def try_extract():
            if not self.is_valid_url(url):
                raise Exception(f"Invalid URL: {url}")
            text = await self.extractor.extract(url)
            if not text:
                raise Exception("Extraction failed - no content returned")
            return text
            
        try:
            text = await retry_with_backoff(try_extract, max_retries=3)
            self.sheets.update_row(row['id'], {
                "content_ts": self.now(),
                "retry_count_content": "0"  # Reset retry count on success
            })
            return {
                **state,
                "current_row": row,
                "text": text,
                "rows": state['rows'][1:]  # Remove the processed row
            }
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            # Safely handle retry count
            retry_count = row.get('retry_count_content', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            self.sheets.update_row(row['id'], {
                "status": "error",
                "retry_count_content": str(current_retry + 1),  # Convert to string for Google Sheets
                "content_ts": self.now()
            })
            return {
                **state,
                "current_row": row,
                "error": str(e),
                "rows": state['rows'][1:]  # Remove the processed row
            }

    async def generate_tweets_node(self, state):
        if state.get('error'):
            logger.error(f"Error in state: {state['error']}")
            return state
            
        if not state.get('text'):
            error_msg = "No text content available for tweet generation"
            logger.error(error_msg)
            return {**state, "error": error_msg}
            
        text = state["text"]
        current_row = state["current_row"]
        
        logger.info(f"Generating tweets for text: {text[:100]}...")
        
        prompt = f"""Generate 6 engaging tweets about the following content. Each tweet should be unique and include relevant hashtags.

Content: {text}

Format each tweet as a JSON object with these exact fields:
- text: The tweet text (under 280 characters)
- hashtags: List of relevant hashtags

Return the tweets as a JSON array. Example format:
[
  {{
    "text": "Exploring blockchain technology and its impact on finance",
    "hashtags": ["Blockchain", "Finance"]
  }},
  {{
    "text": "The future of decentralized applications",
    "hashtags": ["DApps", "Web3"]
  }}
]

Do not include any numbering or additional text. Return only the JSON array."""
        
        try:
            logger.info("Calling LLM to generate tweets...")
            response = await self.llm.generate_content(prompt)
            logger.info(f"LLM response: {response}")
            
            # Parse the response into a list of tweet objects
            tweets = []
            try:
                # Remove markdown code block markers if present
                response = response.strip('```json\n').strip('```')
                # Remove any numbering or additional text
                response = response.split('\n')
                response = [line for line in response if line.strip() and not line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.'))]
                response = '\n'.join(response)
                
                # Parse the JSON array
                tweet_list = json.loads(response)
                if not isinstance(tweet_list, list):
                    tweet_list = [tweet_list]
                
                for i, tweet in enumerate(tweet_list):
                    if isinstance(tweet, dict):
                        # Handle nested text object
                        tweet_text = tweet.get('text', '')
                        if isinstance(tweet_text, dict):
                            tweet_text = tweet_text.get('text', '')
                            
                        # Handle nested hashtags
                        hashtags = tweet.get('hashtags', ["#blockchain", "#crypto"])
                        if isinstance(hashtags, dict):
                            hashtags = hashtags.get('hashtags', ["#blockchain", "#crypto"])
                        
                        # Create a properly formatted tweet object
                        formatted_tweet = {
                            "index": i + 1,
                            "text": tweet_text,
                            "hashtags": hashtags,
                            "gen_ts": self.now()
                        }
                        tweets.append(formatted_tweet)
                logger.info(f"Parsed {len(tweets)} tweets from JSON response")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse response as JSON: {str(e)}")
                # If not JSON, split by newlines and create tweet objects
                for i, line in enumerate(response.split('\n')):
                    line = line.strip()
                    if line and not line.startswith(('1.', '2.', '3.', '4.', '5.', '6.')):
                        tweets.append({
                            "index": i + 1,
                            "text": line,
                            "hashtags": ["#blockchain", "#crypto"],
                            "gen_ts": self.now()
                        })
                logger.info(f"Created {len(tweets)} tweets from newline-split response")
            
            if not tweets:
                error_msg = "No tweets generated"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            # Update the Google Sheet with the generated tweets
            logger.info(f"Updating Google Sheet with {len(tweets)} tweets")
            self.sheets.update_row(current_row['id'], {
                "generate_ts": self.now(),
                "retry_count_generate": "0",
                "tweets": json.dumps(tweets)  # Store as properly formatted JSON string
            })
            
            logger.info(f"Generated {len(tweets)} tweets successfully")
            return {**state, "tweets": tweets}
        except Exception as e:
            error_msg = f"Error generating tweets: {str(e)}"
            logger.error(error_msg)
            # Safely handle retry count
            retry_count = current_row.get('retry_count_generate', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_generate": str(current_retry + 1),
                "generate_ts": self.now()
            })
            return {**state, "error": error_msg}

    async def store_tweets_node(self, state):
        if state.get('error'):
            logger.error(f"Error in state: {state['error']}")
            return state
            
        if not state.get('tweets'):
            error_msg = "No tweets to store"
            logger.error(error_msg)
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        tweets = state["tweets"]
        
        try:
            logger.info(f"Storing {len(tweets)} tweets")
            
            # Process tweets to ensure correct structure
            processed_tweets = []
            for tweet in tweets:
                # Handle nested text object
                tweet_text = tweet.get('text', '')
                if isinstance(tweet_text, dict):
                    tweet_text = tweet_text.get('text', '')
                    
                # Handle nested hashtags
                hashtags = tweet.get('hashtags', ["#blockchain", "#crypto"])
                if isinstance(hashtags, dict):
                    hashtags = hashtags.get('hashtags', ["#blockchain", "#crypto"])
                
                # Create properly formatted tweet
                processed_tweet = {
                    "index": tweet.get('index', len(processed_tweets) + 1),
                    "text": tweet_text,
                    "hashtags": hashtags,
                    "gen_ts": tweet.get('gen_ts', self.now())
                }
                processed_tweets.append(processed_tweet)
            
            # Store the processed tweets
            self.tweet_storer.store_llm_tweets(current_row['id'], processed_tweets)
            logger.info("Tweets stored successfully")
            
            # Update the Google Sheet with the processed tweets
            self.sheets.update_row(current_row['id'], {
                "store_ts": self.now(),
                "retry_count_store": "0",
                "tweets": json.dumps(processed_tweets)
            })
            
            return {**state, "stored": True, "tweets": processed_tweets}
        except Exception as e:
            error_msg = f"Error storing tweets: {str(e)}"
            logger.error(error_msg)
            # Safely handle retry count
            retry_count = current_row.get('retry_count_store', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_store": str(current_retry + 1),
                "store_ts": self.now()
            })
            return {**state, "error": error_msg}

    async def post_to_twitter_node(self, state):
        if state.get('error'):
            logger.error(f"Error in state: {state['error']}")
            return state
            
        if not state.get('tweets'):
            error_msg = "No tweets available to post"
            logger.error(error_msg)
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        tweets = state["tweets"]
        
        try:
            # Post each tweet
            for tweet in tweets:
                logger.info(f"Posting tweet: {tweet['text'][:50]}...")
                self.twitter.post_tweet(tweet['text'])
                logger.info("Tweet posted successfully")
                
            # Update the Google Sheet
            self.sheets.update_row(current_row['id'], {
                "post_ts": self.now(),
                "retry_count_post": "0",
                "status": "in_progress"
            })
            
            logger.info("All tweets posted successfully")
            return {**state, "posted": True}
        except Exception as e:
            error_msg = f"Error posting tweets: {str(e)}"
            logger.error(error_msg)
            # Safely handle retry count
            retry_count = current_row.get('retry_count_post', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_post": str(current_retry + 1),
                "post_ts": self.now()
            })
            return {**state, "error": error_msg}

    async def post_to_bsky_node(self, state):
        if "error" in state:
            return state
            
        if not state.get('posted'):
            logger.error("No tweets posted to Bluesky")
            return {**state, "error": "No tweets posted"}
            
        current_row = state["current_row"]
        
        try:
            # Get posted tweets from database
            posted_tweets = self.db.get_posted_tweets(current_row['id'])
            if not posted_tweets:
                logger.error("No posted tweets found")
                return {**state, "error": "No posted tweets found"}
                
            # Post each tweet to Bluesky
            for tweet in posted_tweets:
                self.bsky.post_tweet(tweet['text'])
                self.db.update_tweet_status(tweet['id'], "posted_to_bsky")
                
            self.sheets.update_row(current_row['id'], {
                "bsky_ts": self.now(),
                "retry_count_bsky": "0",
                "status": "completed"
            })
            return {**state, "posted_to_bsky": True}
        except Exception as e:
            logger.error(f"Error posting to Bluesky: {str(e)}")
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_bsky": str(int(current_row.get('retry_count_bsky', '0')) + 1),
                "bsky_ts": self.now()
            })
            return {**state, "error": str(e)}

    async def engage_posts_node(self, state):
        if "error" in state:
            return state
            
        if not state.get('posted_to_bsky'):
            logger.error("No tweets posted to Bluesky")
            return {**state, "error": "No tweets posted to Bluesky"}
            
        current_row = state["current_row"]
        
        try:
            # Get posted tweets from database
            posted_tweets = self.db.get_posted_tweets(current_row['id'])
            if not posted_tweets:
                logger.error("No posted tweets found")
                return {**state, "error": "No posted tweets found"}
                
            # Engage with each tweet
            for tweet in posted_tweets:
                self.bsky.like_post(tweet['bsky_id'])
                self.bsky.repost_post(tweet['bsky_id'])
                
            self.sheets.update_row(current_row['id'], {
                "engagement_ts": self.now(),
                "retry_count_engagement": "0",
                "status": "completed"
            })
            return {**state, "engaged": True}
        except Exception as e:
            logger.error(f"Error engaging with posts: {str(e)}")
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_engagement": str(int(current_row.get('retry_count_engagement', '0')) + 1),
                "engagement_ts": self.now()
            })
            return {**state, "error": str(e)}

    async def schedule_followups_node(self, state):
        if "error" in state:
            return state
            
        if not state.get('engaged'):
            logger.error("No posts were engaged with")
            return {**state, "error": "No posts were engaged with"}
            
        current_row = state["current_row"]
        
        try:
            # Get posted tweets from database
            posted_tweets = self.db.get_posted_tweets(current_row['id'])
            if not posted_tweets:
                logger.error("No posted tweets found")
                return {**state, "error": "No posted tweets found"}
                
            # Schedule follow-up tweets
            for tweet in posted_tweets:
                followup_tweet = self.generate_followup_tweet(tweet['text'])
                scheduled_time = self.calculate_followup_time()
                self.db.store_tweet(current_row['id'], followup_tweet, scheduled_time)
                
            self.sheets.update_row(current_row['id'], {
                "followup_scheduled_ts": self.now(),
                "retry_count_followup": "0",
                "status": "completed"
            })
            return {**state, "followups_scheduled": True}
        except Exception as e:
            logger.error(f"Error scheduling follow-ups: {str(e)}")
            self.sheets.update_row(current_row['id'], {
                "status": "error",
                "retry_count_followup": str(int(current_row.get('retry_count_followup', '0')) + 1),
                "followup_scheduled_ts": self.now()
            })
            return {**state, "error": str(e)}

    def completion_node(self, state):
        if not state.get('current_row'):
            logger.info("No current row to complete")
            return {"end": True}
            
        row_id = state['current_row']['id']
        status = "complete" if not state.get('error') else "error"
        self.sheets.update_row(row_id, {"status": status, "last_update_ts": self.now()})
        return {"end": True}

    def build_workflow_graph(self):
        from typing import TypedDict, List, Dict, Any, Optional
        from langgraph.graph import StateGraph

        class WorkflowState(TypedDict):
            rows: List[Dict[str, Any]]
            current_row: Optional[Dict[str, Any]]
            text: Optional[str]
            tweets: Optional[List[Dict[str, Any]]]
            error: Optional[str]

        graph = StateGraph(WorkflowState)
        
        # Add nodes
        graph.add_node("batch_retrieval", RunnableLambda(self.batch_retrieval))
        graph.add_node("extract_content", RunnableLambda(self.extract_content_node))
        graph.add_node("generate_tweets", RunnableLambda(self.generate_tweets_node))
        graph.add_node("store_tweets", RunnableLambda(self.store_tweets_node))
        graph.add_node("post_to_twitter", RunnableLambda(self.post_to_twitter_node))
        graph.add_node("post_to_bsky", RunnableLambda(self.post_to_bsky_node))
        graph.add_node("engage_posts", RunnableLambda(self.engage_posts_node))
        graph.add_node("schedule_followups", RunnableLambda(self.schedule_followups_node))
        graph.add_node("completion", RunnableLambda(self.completion_node))

        # Add edges
        graph.add_edge("batch_retrieval", "extract_content")
        graph.add_edge("extract_content", "generate_tweets")
        graph.add_edge("generate_tweets", "store_tweets")
        graph.add_edge("store_tweets", "post_to_twitter")
        graph.add_edge("post_to_twitter", "post_to_bsky")
        graph.add_edge("post_to_bsky", "engage_posts")
        graph.add_edge("engage_posts", "schedule_followups")
        graph.add_edge("schedule_followups", "completion")
        graph.add_edge("completion", END)

        # Add error handling edges
        def has_error(state):
            return "error" in state

        graph.add_conditional_edges(
            "batch_retrieval",
            {
                "extract_content": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "extract_content",
            {
                "generate_tweets": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "generate_tweets",
            {
                "store_tweets": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "store_tweets",
            {
                "post_to_twitter": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "post_to_twitter",
            {
                "post_to_bsky": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "post_to_bsky",
            {
                "engage_posts": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "engage_posts",
            {
                "schedule_followups": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "schedule_followups",
            {
                "completion": lambda x: True
            }
        )

        # Set entry point
        graph.set_entry_point("batch_retrieval")
        
        # Compile the graph
        return graph.compile() 