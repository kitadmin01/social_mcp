# Placeholder for posting to Bluesky via API

import os
import aiohttp
import asyncio
from typing import Optional, List, Dict
import logging
import time
from datetime import datetime, timezone
from common.google_sheets import GoogleSheetsClient
import json

logger = logging.getLogger(__name__)

class BlueskyAPI:
    def __init__(self):
        self.api_key = os.getenv('BLUESKY_API_KEY')
        self.api_password = os.getenv('BLUESKY_API_PASSWORD')
        self.session = None
        self.access_jwt = None
        logger.info("BlueskyAPI initialized")

    async def _ensure_session(self):
        """Ensure we have an active session and access token."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        if self.access_jwt is None:
            self.access_jwt = await self._login()
            self.session.headers.update({'Authorization': f'Bearer {self.access_jwt}'})

    async def _login(self) -> str:
        """Login to Bluesky and get access token."""
        try:
            url = 'https://bsky.social/xrpc/com.atproto.server.createSession'
            payload = {"identifier": self.api_key, "password": self.api_password}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    logger.info("Successfully logged in to Bluesky")
                    return data['accessJwt']
        except Exception as e:
            logger.error(f"Failed to login to Bluesky: {str(e)}")
            raise

    async def create_post(self, text: str, repo: Optional[str] = None) -> dict:
        """Create a post on Bluesky.
        
        Args:
            text (str): The text content of the post
            repo (Optional[str]): The repository (DID) to post to. Defaults to the authenticated user's DID.
            
        Returns:
            dict: The API response containing the created post's URI and CID
        """
        try:
            await self._ensure_session()
            url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
            if repo is None:
                repo = self.api_key  # This should be the DID (Decentralized Identifier)
                
            # Get current timestamp in the correct format for Bluesky
            created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            payload = {
                "repo": repo,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "createdAt": created_at,
                    "langs": ["en"]
                }
            }
            
            logger.info(f"Creating Bluesky post with text: {text[:50]}...")
            async with self.session.post(url, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()
                logger.info("Successfully created Bluesky post")
                return result
        except aiohttp.ClientResponseError as e:
            if e.status == 400:
                logger.error(f"Bad request. Response: {await e.response.text()}")
            raise
        except Exception as e:
            logger.error(f"Error creating Bluesky post: {str(e)}")
            raise

    async def post_from_sheets(self, sheet_name: str = "Sheet1", max_posts: int = 1) -> List[Dict]:
        """Post content from Google Sheets to Bluesky.
        
        Args:
            sheet_name (str): Name of the sheet containing content (default: "Sheet1")
            max_posts (int): Maximum number of posts to make
            
        Returns:
            List[Dict]: Results of the posting operations
        """
        try:
            # Initialize Google Sheets client
            credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "google_sheets_credentials.json")
            sheet_id = os.getenv('GOOGLE_SHEET_ID')
            if not sheet_id:
                raise ValueError("GOOGLE_SHEET_ID environment variable is not set")
            sheets = GoogleSheetsClient(credentials_path, sheet_id)
            
            logger.info(f"Fetching tweets from sheet: {sheet_name}")
            rows = sheets.get_rows()
            
            if not rows:
                logger.warning("No rows found in sheet")
                return []
            
            results = []
            posts_made = 0
            
            for row in rows:
                if posts_made >= max_posts:
                    break
                    
                try:
                    # Get tweets from the "tweets" column
                    tweets_json = row.get('tweets', '[]')
                    if not tweets_json:
                        logger.warning("No tweets found in row, skipping")
                        continue
                        
                    # Parse tweets JSON
                    try:
                        tweets = json.loads(tweets_json)
                        if not isinstance(tweets, list):
                            tweets = [tweets]
                    except json.JSONDecodeError:
                        logger.warning("Invalid tweets JSON, skipping")
                        continue
                    
                    # Post each tweet
                    for tweet in tweets:
                        if posts_made >= max_posts:
                            break
                            
                        text = tweet.get('text', '').strip()
                        if not text:
                            logger.warning("Empty tweet text found, skipping")
                            continue
                            
                        logger.info(f"Posting tweet: {text[:50]}...")
                        result = await self.create_post(text)
                        results.append({
                            'text': text,
                            'status': 'success',
                            'result': result
                        })
                        posts_made += 1
                        logger.info(f"Successfully posted tweet {posts_made}/{max_posts}")
                        
                        # Add delay between posts
                        await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error posting tweets: {str(e)}")
                    results.append({
                        'text': text if 'text' in locals() else 'unknown',
                        'status': 'error',
                        'error': str(e)
                    })
                    continue
            
            logger.info(f"Completed posting {len(results)} items to Bluesky")
            return results
            
        except Exception as e:
            logger.error(f"Error in post_from_sheets: {str(e)}")
            raise

    async def search_blockchain_posts(self, limit: int = 5) -> list:
        """Search for blockchain-related posts.
        
        Args:
            limit (int): Maximum number of posts to return (default: 5)
            
        Returns:
            list: List of posts matching the search criteria
        """
        try:
            await self._ensure_session()
            url = 'https://bsky.social/xrpc/app.bsky.feed.searchPosts'
            params = {
                'q': '#blockchain',
                'limit': limit
            }
            
            logger.info(f"Searching for blockchain posts (limit: {limit})")
            async with self.session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                posts = data.get('posts', [])
                logger.info(f"Found {len(posts)} blockchain posts")
                return posts
            
        except aiohttp.ClientResponseError as e:
            logger.error(f"Error searching posts: {str(e)}")
            if e.status == 403:
                logger.error("Authentication failed. Please check your API credentials.")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching posts: {str(e)}")
            raise

    async def like_post(self, uri: str, cid: str, repo: Optional[str] = None) -> dict:
        """Like a post on Bluesky.
        
        Args:
            uri (str): The URI of the post to like
            cid (str): The CID of the post to like
            repo (Optional[str]): The repository (DID) to like from. Defaults to the authenticated user's DID.
            
        Returns:
            dict: The API response containing the created like's URI and CID
        """
        try:
            await self._ensure_session()
            url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
            if repo is None:
                repo = self.api_key
                
            created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            payload = {
                "repo": repo,
                "collection": "app.bsky.feed.like",
                "record": {
                    "$type": "app.bsky.feed.like",
                    "subject": {
                        "uri": uri,
                        "cid": cid
                    },
                    "createdAt": created_at
                }
            }
            
            logger.info(f"Liking post: {uri}")
            async with self.session.post(url, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()
                logger.info("Successfully liked post")
                return result
            
        except aiohttp.ClientResponseError as e:
            if e.status == 400:
                logger.error(f"Bad request. Response: {await e.response.text()}")
            raise
        except Exception as e:
            logger.error(f"Error liking post: {str(e)}")
            raise

    async def search_and_like_blockchain(self, like_count: int = 1) -> list:
        """Search for blockchain-related posts and like them.
        
        Args:
            like_count (int): Number of posts to like (default: 1)
            
        Returns:
            list: Results of the like operations
        """
        try:
            logger.info(f"Searching for blockchain posts to like (count: {like_count})...")
            posts = await self.search_blockchain_posts(limit=like_count)
            
            results = []
            for i, post in enumerate(posts, 1):
                try:
                    uri = post.get('uri')
                    cid = post.get('cid')
                    if not uri or not cid:
                        logger.warning(f"Post {i} missing URI or CID, skipping")
                        continue
                        
                    logger.info(f"Liking post {i}/{len(posts)}: {uri}")
                    result = await self.like_post(uri, cid)
                    results.append(result)
                    logger.info(f"Successfully liked post {i}")
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Failed to like post {i}: {str(e)}")
                    continue
            
            logger.info(f"Completed liking {len(results)} posts")
            return results
            
        except Exception as e:
            logger.error(f"Error in search_and_like_blockchain: {str(e)}")
            raise

    def post(self, text: str) -> bool:
        """Post a text to Bluesky."""
        try:
            url = f"{self.base_url}/com.atproto.repo.createRecord"
            payload = {
                "repo": self.did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": text,
                    "createdAt": datetime.now().isoformat(),
                    "$type": "app.bsky.feed.post"
                }
            }
            resp = self.session.post(url, json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error posting to Bluesky: {str(e)}")
            return False
