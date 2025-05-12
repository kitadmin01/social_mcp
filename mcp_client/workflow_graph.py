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
from typing import Dict, Any

from common.google_sheets import GoogleSheetsClient
from common.llm_orchestrator import LLMOrchestrator
from common.retry_utils import retry_with_backoff
from mcp_server.tools.extract_content import ExtractContent
from mcp_server.tools.store_tweets import StoreTweets
from mcp_server.tools.post_tweets import TwitterPlaywright
from mcp_server.tools.bsky import BlueskyAPI
from mcp_server.tools.schedule_post import SchedulePost
from mcp_server.tools.telegram_post import TelegramPoster

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class WorkflowGraph:
    def __init__(self, batch_size=5, engage_count=7):
        self.M = batch_size
        self.ENGAGE_COUNT = engage_count
        
        # Get search terms from environment
        search_terms = os.getenv('SEARCH_TERMS', '#blockchain,#crypto,#web3,#defi,#nft')
        self.search_terms = [term.strip() for term in search_terms.split(',')]
        logger.info(f"Initialized with search terms: {self.search_terms}")
        
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
        self.telegram = TelegramPoster()

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

    async def batch_retrieval(self, state):
        """Retrieve content from URLs in batches.
        
        Args:
            state (dict): The current workflow state
            
        Returns:
            dict: Updated state with rows to process
        """
        try:
            # Check Sheet1 first for pending URLs
            sheet1 = self.sheets.sheet.worksheet("Sheet1")
            if not sheet1:
                logger.error("Sheet1 not found")
                return {**state, "error": "Sheet1 not found"}
            
            records1 = sheet1.get_all_records()
            pending_rows1 = [i for i, row in enumerate(records1, start=2) 
                           if not row.get('status') or row.get('status').lower() == 'pending']
            
            if pending_rows1:
                logger.info(f"Found {len(pending_rows1)} pending URLs in Sheet1")
                # Process up to M URLs from Sheet1
                rows_to_process = pending_rows1[:self.M]
                valid_rows = []
                
                for row_idx in rows_to_process:
                    try:
                        url = records1[row_idx-2].get('url')
                        if not url:
                            logger.warning(f"No URL found in row {row_idx}")
                            continue
                            
                        logger.info(f"Processing URL from Sheet1: {url}")
                        # Update status to in_progress
                        sheet1.update_cell(row_idx, 3, 'in_progress')
                        sheet1.update_cell(row_idx, 4, self.now())
                        
                        valid_rows.append({
                            'id': row_idx,
                            'url': url,
                            'sheet': 'Sheet1'
                        })
                            
                    except Exception as e:
                        logger.error(f"Error processing URL in Sheet1 row {row_idx}: {str(e)}")
                        continue
                
                if valid_rows:
                    logger.info(f"Returning {len(valid_rows)} rows from Sheet1 for processing")
                    return {**state, "rows": valid_rows, "engagement_only": False}
                        
            # If no pending URLs in Sheet1, check Sheet2
            sheet2 = self.sheets.sheet.worksheet("Sheet2")
            if not sheet2:
                logger.error("Sheet2 not found")
                return {**state, "error": "Sheet2 not found"}
            
            records2 = sheet2.get_all_records()
            # Only get rows with exactly 'pending' status (case-insensitive)
            pending_rows2 = [i for i, row in enumerate(records2, start=2) 
                           if row.get('status', '').lower() == 'pending']
            
            if pending_rows2:
                logger.info(f"Found {len(pending_rows2)} pending URLs in Sheet2")
                # Process up to M URLs from Sheet2
                rows_to_process = pending_rows2[:self.M]
                valid_rows = []
                
                for row_idx in rows_to_process:
                    try:
                        # Use tele_urls instead of url for Sheet2
                        url = records2[row_idx-2].get('tele_urls')
                        if not url:
                            logger.warning(f"No tele_urls found in row {row_idx}")
                            continue
                            
                        logger.info(f"Processing URL from Sheet2: {url}")
                        # Update status to in_progress
                        sheet2.update_cell(row_idx, 3, 'in_progress')
                        sheet2.update_cell(row_idx, 4, self.now())
                        
                        valid_rows.append({
                            'id': row_idx,
                            'url': url,
                            'sheet': 'Sheet2'
                        })
                            
                    except Exception as e:
                        logger.error(f"Error processing URL in Sheet2 row {row_idx}: {str(e)}")
                        continue
                
                if valid_rows:
                    logger.info(f"Returning {len(valid_rows)} rows from Sheet2 for processing")
                    return {**state, "rows": valid_rows, "engagement_only": False}
                
            logger.info("No pending URLs found in either sheet, proceeding with engagement only")
            return {**state, "rows": [], "engagement_only": True}
            
        except Exception as e:
            logger.error(f"Error in batch_retrieval: {str(e)}")
            return {**state, "error": str(e)}

    async def extract_content_node(self, state):
        if not state.get('rows'):
            return state
            
        # Get the first row to process
        row = state['rows'][0]
        url = row.get('url', '')
        
        async def try_extract():
            if not self.is_valid_url(url):
                raise Exception(f"Invalid URL: {url}")
            text = await self.extractor.extract(url)
            if not text:
                raise Exception("Extraction failed - no content returned")
            return text
            
        try:
            text = await retry_with_backoff(try_extract, max_retries=3)
            
            # Update the appropriate sheet
            if row['sheet'] == 'Sheet1':
                sheet = self.sheets.sheet.worksheet("Sheet1")
                headers = sheet.row_values(1)
                col_indices = {col: headers.index(col) + 1 for col in headers}
                sheet.update_cell(row['id'], col_indices['content_ts'], self.now())
                sheet.update_cell(row['id'], col_indices['retry_count_content'], "0")
            else:  # Sheet2
                sheet = self.sheets.sheet.worksheet("Sheet2")
                headers = sheet.row_values(1)
                col_indices = {col: headers.index(col) + 1 for col in headers}
                sheet.update_cell(row['id'], col_indices['last_update_ts'], self.now())
                
            return {
                **state,
                "current_row": row,
                "text": text,
                "rows": state['rows'][1:]  # Remove the processed row
            }
        except Exception as e:
            # Update error in the appropriate sheet
            if row['sheet'] == 'Sheet1':
                sheet = self.sheets.sheet.worksheet("Sheet1")
                headers = sheet.row_values(1)
                col_indices = {col: headers.index(col) + 1 for col in headers}
                retry_count = row.get('retry_count_content', '0')
                try:
                    current_retry = int(retry_count) if retry_count else 0
                except ValueError:
                    current_retry = 0
                sheet.update_cell(row['id'], col_indices['status'], "error")
                sheet.update_cell(row['id'], col_indices['retry_count_content'], str(current_retry + 1))
                sheet.update_cell(row['id'], col_indices['content_ts'], self.now())
            else:  # Sheet2
                sheet = self.sheets.sheet.worksheet("Sheet2")
                headers = sheet.row_values(1)
                col_indices = {col: headers.index(col) + 1 for col in headers}
                sheet.update_cell(row['id'], col_indices['status'], "error")
                sheet.update_cell(row['id'], col_indices['error'], str(e))
                sheet.update_cell(row['id'], col_indices['last_update_ts'], self.now())
                
            return {
                **state,
                "current_row": row,
                "error": str(e),
                "rows": state['rows'][1:]  # Remove the processed row
            }

    async def generate_tweets_node(self, state):
        if state.get('error'):
            return state
            
        if not state.get('text'):
            error_msg = "No text content available for tweet generation"
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        if current_row.get('sheet') != 'Sheet1':
            # Skip if not from Sheet1
            return {**state, "skipped": True, "reason": "Not a Twitter/Bluesky URL"}
            
        text = state["text"]
        
        try:
            # Generate tweets using LLM
            prompt = f"""Based on the following content, generate 3 engaging tweets about blockchain/crypto. 
            Each tweet should be unique, informative, and include relevant hashtags.
            Format the response as a JSON array of objects with 'text' field.
            Content: {text}"""
            
            response = await self.llm.generate_content(prompt)
            if not response:
                raise Exception("No response from LLM")
                
            # Parse the response to get tweets
            try:
                # Remove markdown code block if present
                if response.startswith('```json'):
                    response = response[7:]
                if response.endswith('```'):
                    response = response[:-3]
                response = response.strip()
                
                # Parse JSON
                raw_tweets = json.loads(response)
                if not isinstance(raw_tweets, list):
                    raw_tweets = [{"text": response}]
                
                # Format tweets according to required structure
                now = datetime.utcnow().isoformat()
                formatted_tweets = []
                
                for i, tweet in enumerate(raw_tweets, 1):
                    # Extract hashtags from the tweet text
                    hashtags = []
                    words = tweet['text'].split()
                    for word in words:
                        if word.startswith('#'):
                            hashtags.append(word[1:])  # Remove # symbol
                    
                    formatted_tweet = {
                        "index": i,
                        "text": tweet['text'],
                        "hashtags": hashtags,
                        "gen_ts": now
                    }
                    formatted_tweets.append(formatted_tweet)
                
            except json.JSONDecodeError:
                # If response is not valid JSON, create a single tweet
                now = datetime.utcnow().isoformat()
                hashtags = []
                words = response.split()
                for word in words:
                    if word.startswith('#'):
                        hashtags.append(word[1:])
                
                formatted_tweets = [{
                    "index": 1,
                    "text": response,
                    "hashtags": hashtags,
                    "gen_ts": now
                }]
            
            # Update Sheet1
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            sheet.update_cell(current_row['id'], col_indices['generate_ts'], self.now())
            sheet.update_cell(current_row['id'], col_indices['tweets'], json.dumps(formatted_tweets))
            
            return {**state, "tweets": formatted_tweets}
        except Exception as e:
            error_msg = f"Error generating tweets: {str(e)}"
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            retry_count = current_row.get('retry_count_generate', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            sheet.update_cell(current_row['id'], col_indices['status'], "error")
            sheet.update_cell(current_row['id'], col_indices['retry_count_generate'], str(current_retry + 1))
            sheet.update_cell(current_row['id'], col_indices['generate_ts'], self.now())
            
            return {**state, "error": error_msg}

    async def store_tweets_node(self, state):
        if state.get('error'):
            return state
            
        if not state.get('tweets'):
            error_msg = "No tweets to store"
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        if current_row.get('sheet') != 'Sheet1':
            # Skip if not from Sheet1
            return {**state, "skipped": True, "reason": "Not a Twitter/Bluesky URL"}
            
        tweets = state["tweets"]
        
        try:
            # Store tweets in Sheet1
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            # Update timestamps and status
            sheet.update_cell(current_row['id'], col_indices['store_ts'], self.now())
            sheet.update_cell(current_row['id'], col_indices['tweets'], json.dumps(tweets))
            
            return {**state, "stored": True}
        except Exception as e:
            error_msg = f"Error storing tweets: {str(e)}"
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            # Update error status
            sheet.update_cell(current_row['id'], col_indices['status'], "error")
            sheet.update_cell(current_row['id'], col_indices['store_ts'], self.now())
            
            return {**state, "error": error_msg}

    async def post_to_twitter_node(self, state):
        if state.get('error'):
            return state
            
        if not state.get('tweets'):
            error_msg = "No tweets available to post"
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        if current_row.get('sheet') != 'Sheet1':
            # Skip if not from Sheet1
            return {**state, "skipped": True, "reason": "Not a Twitter/Bluesky URL"}
            
        tweets = state["tweets"]
        
        try:
            # Post each tweet
            for tweet in tweets:
                await self.twitter.post_tweet(tweet['text'])
                
            # Update Sheet1
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            sheet.update_cell(current_row['id'], col_indices['twitter_result'], "success")
            sheet.update_cell(current_row['id'], col_indices['retry_count_post_twitter'], "0")
            
            return {**state, "posted": True}
        except Exception as e:
            error_msg = f"Error posting tweets: {str(e)}"
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            retry_count = current_row.get('retry_count_post_twitter', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            sheet.update_cell(current_row['id'], col_indices['twitter_result'], "error")
            sheet.update_cell(current_row['id'], col_indices['retry_count_post_twitter'], str(current_retry + 1))
            
            return {**state, "error": error_msg}

    async def post_to_bsky_node(self, state):
        if state.get('error'):
            return state
            
        if not state.get('tweets'):
            error_msg = "No tweets available to post to Bluesky"
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        if current_row.get('sheet') != 'Sheet1':
            # Skip if not from Sheet1
            return {**state, "skipped": True, "reason": "Not a Twitter/Bluesky URL"}
            
        tweets = state["tweets"]
        
        try:
            # Post each tweet to Bluesky
            for tweet in tweets:
                await self.bsky.create_post(tweet['text'])
                
            # Update Sheet1
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            sheet.update_cell(current_row['id'], col_indices['bsky_result'], "success")
            sheet.update_cell(current_row['id'], col_indices['retry_count_post_bsky'], "0")
            
            return {**state, "posted_to_bsky": True}
        except Exception as e:
            error_msg = f"Error posting to Bluesky: {str(e)}"
            sheet = self.sheets.sheet.worksheet("Sheet1")
            headers = sheet.row_values(1)
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            retry_count = current_row.get('retry_count_post_bsky', '0')
            try:
                current_retry = int(retry_count) if retry_count else 0
            except ValueError:
                current_retry = 0
                
            sheet.update_cell(current_row['id'], col_indices['bsky_result'], "error")
            sheet.update_cell(current_row['id'], col_indices['retry_count_post_bsky'], str(current_retry + 1))
            
            return {**state, "error": error_msg}

    def get_random_search_term(self):
        """Get a random search term from the configured list."""
        if not self.search_terms:
            return "#blockchain"  # fallback to default
        return random.choice(self.search_terms)

    async def engage_posts_node(self, state):
        if state.get('error'):
            return state
            
        # Allow engagement even if no tweets were posted
        if state.get('engagement_only') or state.get('posted'):
            try:
                # Get random search term for this engagement cycle
                search_term = self.get_random_search_term()
                logger.info(f"Using search term for engagement: {search_term}")
                
                # Like tweets with random search term
                logger.info(f"Engaging with Twitter posts using term: {search_term}")
                await self.twitter.search_and_like_tweets(search_term=search_term, max_likes=5)
                logger.info("Twitter engagement completed")
                
                # Like posts on Bluesky with same search term
                logger.info(f"Engaging with Bluesky posts using term: {search_term}")
                await self.bsky.search_and_like_blockchain(search_term=search_term, like_count=3)
                logger.info("Bluesky engagement completed")
                
                # Update the Google Sheet if we have a current row
                if state.get('current_row'):
                    self.sheets.update_row(state['current_row']['id'], {
                        "engagement_ts": self.now(),
                        "retry_count_engagement": "0",
                        "status": "in_progress"
                    })
                
                return {**state, "engaged": True}
            except Exception as e:
                error_msg = f"Error engaging with posts: {str(e)}"
                logger.error(error_msg)
                if state.get('current_row'):
                    retry_count = state['current_row'].get('retry_count_engagement', '0')
                    try:
                        current_retry = int(retry_count) if retry_count else 0
                    except ValueError:
                        current_retry = 0
                        
                    self.sheets.update_row(state['current_row']['id'], {
                        "status": "error",
                        "retry_count_engagement": str(current_retry + 1),
                        "engagement_ts": self.now()
                    })
                return {**state, "error": error_msg}
        
        return state

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

    async def post_to_telegram_node(self, state):
        """Post content to Telegram channel."""
        if state.get('error'):
            return state
            
        if not state.get('text'):
            error_msg = "No content available to post to Telegram"
            return {**state, "error": error_msg}
            
        current_row = state["current_row"]
        if current_row.get('sheet') != 'Sheet2':
            # Skip if not from Sheet2
            return {**state, "skipped": True, "reason": "Not a Telegram URL"}
            
        text = state["text"]
        
        try:
            # Get Sheet2
            sheet2 = self.sheets.sheet.worksheet("Sheet2")
            
            # Get headers and verify required columns
            headers = sheet2.row_values(1)
            required_columns = ['status', 'error', 'last_update_ts']
            missing_columns = [col for col in required_columns if col not in headers]
            
            if missing_columns:
                logger.error(f"Missing required columns in Sheet2: {missing_columns}")
                return {**state, "error": f"Missing required columns: {missing_columns}"}
            
            # Get column indices
            col_indices = {col: headers.index(col) + 1 for col in headers}
            
            # Format content for Telegram
            content = {
                'title': 'New Post',
                'content': text,
                'url': current_row.get('url', '')
            }
            
            # Format message for Telegram
            message = self.telegram.format_telegram_message(content)
            if not message:
                raise Exception("Failed to format message for Telegram")
            
            # Post to Telegram
            success = self.telegram.post_to_telegram(message)
            if not success:
                raise Exception("Failed to post to Telegram")
            
            # Update the Google Sheet in Sheet2 with 'complete' status
            sheet2.update_cell(current_row['id'], col_indices['status'], "complete")
            sheet2.update_cell(current_row['id'], col_indices['last_update_ts'], self.now())
            logger.info(f"Successfully posted to Telegram and updated status to complete for row {current_row['id']}")
            
            return {**state, "posted_to_telegram": True}
        except Exception as e:
            error_msg = f"Error posting to Telegram: {str(e)}"
            logger.error(error_msg)
            
            # Update error status in Sheet2
            sheet2.update_cell(current_row['id'], col_indices['status'], "error")
            sheet2.update_cell(current_row['id'], col_indices['error'], error_msg)
            sheet2.update_cell(current_row['id'], col_indices['last_update_ts'], self.now())
            
            return {**state, "error": error_msg}

    async def completion_node(self, state: Dict) -> Dict:
        """Handle workflow completion."""
        try:
            current_row = state.get('current_row')
            if not current_row:
                logger.warning("No current row to complete")
                return {"end": True}
                
            row_id = current_row.get('id')
            sheet_name = current_row.get('sheet', 'Sheet1')
            status = "complete" if not state.get('error') else "error"
            
            # Update the row with completion status
            self.sheets.update_row(sheet_name, row_id, {
                "status": status,
                "last_update_ts": self.now()
            })
            
            logger.info(f"Workflow completed for {sheet_name} - Row {row_id} with status: {status}")
            return {"end": True}
            
        except Exception as e:
            logger.error(f"Error in completion node: {str(e)}")
            return {"end": True, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all platforms.
        
        Returns:
            Dict[str, Any]: Status information for each platform
        """
        return {
            'telegram': self.telegram.get_status() if hasattr(self.telegram, 'get_status') else None,
            'twitter': self.twitter.get_status() if hasattr(self.twitter, 'get_status') else None,
            'bluesky': self.bsky.get_status() if hasattr(self.bsky, 'get_status') else None
        }

    def build_workflow_graph(self):
        from typing import TypedDict, List, Dict, Any, Optional
        from langgraph.graph import StateGraph

        class WorkflowState(TypedDict):
            rows: List[Dict[str, Any]]
            current_row: Optional[Dict[str, Any]]
            text: Optional[str]
            tweets: Optional[List[Dict[str, Any]]]
            error: Optional[str]
            engagement_only: Optional[bool]

        graph = StateGraph(WorkflowState)
        
        # Add nodes
        graph.add_node("batch_retrieval", RunnableLambda(self.batch_retrieval))
        graph.add_node("extract_content", RunnableLambda(self.extract_content_node))
        graph.add_node("post_to_telegram", RunnableLambda(self.post_to_telegram_node))
        graph.add_node("generate_tweets", RunnableLambda(self.generate_tweets_node))
        graph.add_node("store_tweets", RunnableLambda(self.store_tweets_node))
        graph.add_node("post_to_twitter", RunnableLambda(self.post_to_twitter_node))
        graph.add_node("post_to_bsky", RunnableLambda(self.post_to_bsky_node))
        graph.add_node("engage_posts", RunnableLambda(self.engage_posts_node))
        graph.add_node("schedule_followups", RunnableLambda(self.schedule_followups_node))
        graph.add_node("completion", RunnableLambda(self.completion_node))

        # Add edges
        graph.add_edge("batch_retrieval", "extract_content")
        graph.add_edge("extract_content", "post_to_telegram")
        graph.add_edge("post_to_telegram", "generate_tweets")
        graph.add_edge("generate_tweets", "store_tweets")
        graph.add_edge("store_tweets", "post_to_twitter")
        graph.add_edge("post_to_twitter", "post_to_bsky")
        graph.add_edge("post_to_bsky", "engage_posts")
        graph.add_edge("engage_posts", "schedule_followups")
        graph.add_edge("schedule_followups", "completion")
        graph.add_edge("completion", END)

        # Add conditional edges for engagement-only path
        def should_engage_only(state):
            return state.get('engagement_only', False)

        graph.add_conditional_edges(
            "batch_retrieval",
            {
                "extract_content": lambda x: not should_engage_only(x),
                "engage_posts": should_engage_only
            }
        )

        # Add error handling edges
        def has_error(state):
            return "error" in state

        graph.add_conditional_edges(
            "extract_content",
            {
                "post_to_telegram": lambda x: not has_error(x),
                "completion": has_error
            }
        )
        graph.add_conditional_edges(
            "post_to_telegram",
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

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if hasattr(self.twitter, 'close_session'):
                await self.twitter.close_session()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}") 