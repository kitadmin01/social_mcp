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
        """Ensure we have a valid session, refresh if needed."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Check if session is valid by making a test request
            try:
                test_url = 'https://bsky.social/xrpc/com.atproto.server.getSession'
                async with self.session.get(test_url) as resp:
                    if resp.status == 401 or resp.status == 403:
                        logger.warning("Session expired, refreshing...")
                        await self._refresh_session()
                    elif resp.status != 200:
                        logger.warning(f"Session check failed with status {resp.status}, refreshing...")
                        await self._refresh_session()
            except Exception as e:
                logger.warning(f"Session check failed: {str(e)}, refreshing...")
                await self._refresh_session()
                
        except Exception as e:
            logger.error(f"Error ensuring session: {str(e)}")
            raise

    async def _refresh_session(self):
        """Refresh the Bluesky session."""
        try:
            logger.info("Refreshing Bluesky session...")
            
            # Close existing session if any
            if self.session:
                await self.session.close()
            
            # Create new session
            self.session = aiohttp.ClientSession()
            
            # Re-authenticate
            url = 'https://bsky.social/xrpc/com.atproto.server.createSession'
            payload = {
                "identifier": self.api_key,
                "password": self.api_password
            }
            
            async with self.session.post(url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Authentication failed: {error_text}")
                
                data = await resp.json()
                self.access_jwt = data.get('accessJwt')
                
                # Update session headers
                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_jwt}'
                })
                
            logger.info("Successfully refreshed Bluesky session")
            
        except Exception as e:
            logger.error(f"Error refreshing session: {str(e)}")
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

    async def search_blockchain_posts(self, search_term: str, limit: int = 5) -> list:
        """Search for posts using the given search term.
        
        Args:
            search_term (str): The search term to use
            limit (int): Maximum number of posts to return (default: 5)
            
        Returns:
            list: List of posts matching the search criteria
        """
        try:
            await self._ensure_session()
            
            # Try the provided search term first
            try:
                url = 'https://bsky.social/xrpc/app.bsky.feed.searchPosts'
                params = {
                    'q': search_term,
                    'limit': limit
                }
                
                logger.info(f"Searching Bluesky for posts with term: {search_term} (limit: {limit})")
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 400:
                        logger.warning(f"Bluesky search failed for term '{search_term}' with status 400")
                        return []
                        
                    resp.raise_for_status()
                    data = await resp.json()
                    posts = data.get('posts', [])
                    
                    if posts:
                        logger.info(f"Found {len(posts)} posts on Bluesky with term '{search_term}'")
                        return posts
                    else:
                        logger.warning(f"No posts found on Bluesky with term '{search_term}'")
            except Exception as e:
                logger.warning(f"Error searching Bluesky with term '{search_term}': {str(e)}")
                return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error in search_blockchain_posts: {str(e)}")
            return []

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

    async def search_and_like_blockchain(self, search_term: str, like_count: int = 1) -> list:
        """Search for posts using the given search term and like them.
        
        Args:
            search_term (str): The search term to use
            like_count (int): Number of posts to like (default: 1)
            
        Returns:
            list: Results of the like operations
        """
        try:
            logger.info(f"Starting Bluesky engagement with term: '{search_term}' (target likes: {like_count})")
            posts = await self.search_blockchain_posts(search_term=search_term, limit=like_count)
            
            if not posts:
                logger.warning(f"No posts found to like on Bluesky with term '{search_term}'")
                return []
            
            results = []
            for i, post in enumerate(posts, 1):
                try:
                    uri = post.get('uri')
                    cid = post.get('cid')
                    if not uri or not cid:
                        logger.warning(f"Post {i} missing URI or CID, skipping")
                        continue
                    
                    # Check if we've already liked this post
                    if await self._check_if_liked(uri):
                        logger.info(f"Post {i} already liked, skipping")
                        continue
                        
                    logger.info(f"Liking Bluesky post {i}/{len(posts)}: {uri}")
                    result = await self.like_post(uri, cid)
                    results.append(result)
                    logger.info(f"Successfully liked Bluesky post {i}")
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Failed to like Bluesky post {i}: {str(e)}")
                    continue
            
            logger.info(f"Completed Bluesky engagement: liked {len(results)} posts with term '{search_term}'")
            return results
            
        except Exception as e:
            logger.error(f"Error in search_and_like_blockchain: {str(e)}")
            return []

    async def _check_if_liked(self, uri: str) -> bool:
        """Check if a post has already been liked."""
        try:
            await self._ensure_session()
            url = 'https://bsky.social/xrpc/app.bsky.feed.getLikes'
            params = {'uri': uri}
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    likes = data.get('likes', [])
                    return any(like.get('actor', {}).get('did') == self.api_key for like in likes)
                return False
        except Exception as e:
            logger.warning(f"Error checking if post was liked: {str(e)}")
            return False

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
