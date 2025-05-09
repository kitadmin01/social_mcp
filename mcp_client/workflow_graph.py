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
        try:
            # Get Sheet1 for Twitter/Bluesky content
            sheet1 = self.sheets.sheet.worksheet("Sheet1")
            if not sheet1:
                logger.error("Sheet1 not found")
                return {"error": "Sheet1 not found"}
                
            # Get headers and verify required columns for Sheet1
            headers1 = sheet1.row_values(1)
            required_columns1 = ['url', 'status', 'processing_ts']
            missing_columns1 = [col for col in required_columns1 if col not in headers1]
            
            if missing_columns1:
                logger.error(f"Missing required columns in Sheet1: {missing_columns1}")
                return {"error": f"Missing required columns in Sheet1: {missing_columns1}"}
            
            # Get column indices for Sheet1
            col_indices1 = {col: headers1.index(col) + 1 for col in headers1}
            
            # Get pending URLs from Sheet1
            records1 = sheet1.get_all_records()
            pending_urls1 = []
            
            # Find rows where status is empty or "pending" and url is not empty
            for i, record in enumerate(records1, start=2):
                status = record.get('status', '').lower()
                if (not status or status == 'pending') and record.get('url'):
                    pending_urls1.append({
                        'id': i,
                        'url': record['url'],
                        'status': 'in_progress',
                        'sheet': 'Sheet1'
                    })
                    logger.info(f"Found pending URL in Sheet1: {record['url']}")
            
            # If we have pending URLs in Sheet1, process them
            if pending_urls1:
                # Take only the first M URLs
                valid_rows = pending_urls1[:self.M]
                logger.info(f"Processing {len(valid_rows)} URLs from Sheet1")
                
                # Update status for selected rows
                for row in valid_rows:
                    sheet1.update_cell(row['id'], col_indices1['status'], "in_progress")
                    sheet1.update_cell(row['id'], col_indices1['processing_ts'], self.now())
                    logger.info(f"Updated status to in_progress for row {row['id']} in Sheet1")
                
                return {"rows": valid_rows, "current_row": None, "text": None, "tweets": None, "engagement_only": False}
            
            # If no pending URLs in Sheet1, check Sheet2
            sheet2 = self.sheets.sheet.worksheet("Sheet2")
            if not sheet2:
                logger.error("Sheet2 not found")
                return {"error": "Sheet2 not found"}
                
            # Get headers and verify required columns for Sheet2
            headers2 = sheet2.row_values(1)
            required_columns2 = ['tele_urls', 'status', 'error', 'update_ts']
            missing_columns2 = [col for col in required_columns2 if col not in headers2]
            
            if missing_columns2:
                logger.error(f"Missing required columns in Sheet2: {missing_columns2}")
                return {"error": f"Missing required columns in Sheet2: {missing_columns2}"}
            
            # Get column indices for Sheet2
            col_indices2 = {col: headers2.index(col) + 1 for col in headers2}
            
            # Get pending URLs from Sheet2
            records2 = sheet2.get_all_records()
            pending_urls2 = []
            
            # Find rows where status is "pending" and tele_urls is not empty
            for i, record in enumerate(records2, start=2):
                if record.get('status') == 'pending' and record.get('tele_urls'):
                    pending_urls2.append({
                        'id': i,
                        'url': record['tele_urls'],
                        'status': 'in_progress',
                        'sheet': 'Sheet2'
                    })
                    logger.info(f"Found pending URL in Sheet2: {record['tele_urls']}")
            
            # If we have pending URLs in Sheet2, process them
            if pending_urls2:
                # Take only the first M URLs
                valid_rows = pending_urls2[:self.M]
                logger.info(f"Processing {len(valid_rows)} URLs from Sheet2")
                
                # Update status for selected rows
                for row in valid_rows:
                    sheet2.update_cell(row['id'], col_indices2['status'], "in_progress")
                    sheet2.update_cell(row['id'], col_indices2['update_ts'], self.now())
                    logger.info(f"Updated status to in_progress for row {row['id']} in Sheet2")
                
                return {"rows": valid_rows, "current_row": None, "text": None, "tweets": None, "engagement_only": False}
            
            # If no pending URLs in either sheet, continue with engagement
            logger.info("No valid rows found to process, continuing with engagement")
            return {"rows": [], "current_row": None, "text": None, "tweets": None, "engagement_only": True}
            
        except Exception as e:
            logger.error(f"Error in batch_retrieval: {str(e)}")
            return {"error": str(e)}

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
                sheet.update_cell(row['id'], col_indices['update_ts'], self.now())
                
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
                sheet.update_cell(row['id'], col_indices['update_ts'], self.now())
                
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

    async def engage_posts_node(self, state):
        if state.get('error'):
            return state
            
        # Allow engagement even if no tweets were posted
        if state.get('engagement_only') or state.get('posted'):
            try:
                # Like blockchain tweets
                logger.info("Engaging with Twitter posts...")
                await self.twitter.search_and_like_tweets(search_term="#blockchain", max_likes=5)
                logger.info("Twitter engagement completed")
                
                # Like blockchain posts on Bluesky
                logger.info("Engaging with Bluesky posts...")
                await self.bsky.search_and_like_blockchain(like_count=3)
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
            required_columns = ['status', 'error', 'update_ts']
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
            
            # Update the Google Sheet in Sheet2
            sheet2.update_cell(current_row['id'], col_indices['status'], "complete")
            sheet2.update_cell(current_row['id'], col_indices['update_ts'], self.now())
            
            return {**state, "posted_to_telegram": True}
        except Exception as e:
            error_msg = f"Error posting to Telegram: {str(e)}"
            
            # Update error status in Sheet2
            sheet2.update_cell(current_row['id'], col_indices['status'], "error")
            sheet2.update_cell(current_row['id'], col_indices['error'], error_msg)
            sheet2.update_cell(current_row['id'], col_indices['update_ts'], self.now())
            
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