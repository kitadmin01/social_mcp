# Placeholder for posting to Bluesky via API

import os
import requests
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

class BlueskyAPI:
    def __init__(self):
        self.api_key = os.getenv('BLUESKY_API_KEY')
        self.api_password = os.getenv('BLUESKY_API_PASSWORD')
        self.session = requests.Session()
        self.access_jwt = self._login()
        self.session.headers.update({'Authorization': f'Bearer {self.access_jwt}'})

    def _login(self) -> str:
        url = 'https://bsky.social/xrpc/com.atproto.server.createSession'
        payload = {"identifier": self.api_key, "password": self.api_password}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()['accessJwt']

    def create_post(self, text: str, repo: Optional[str] = None) -> dict:
        """Create a post on Bluesky.
        
        Args:
            text (str): The text content of the post
            repo (Optional[str]): The repository (DID) to post to. Defaults to the authenticated user's DID.
            
        Returns:
            dict: The API response containing the created post's URI and CID
        """
        url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
        if repo is None:
            repo = self.api_key  # This should be the DID (Decentralized Identifier)
            
        # Get current timestamp in the correct format for Bluesky
        from datetime import datetime, timezone
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
        
        try:
            resp = self.session.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.error(f"Bad request. Response: {e.response.text}")
            raise

    def search_blockchain_posts(self, limit: int = 5) -> list:
        """Search for blockchain-related posts.
        
        Args:
            limit (int): Maximum number of posts to return (default: 5)
            
        Returns:
            list: List of posts matching the search criteria
        """
        try:
            # Use the authenticated API endpoint
            url = 'https://bsky.social/xrpc/app.bsky.feed.searchPosts'
            params = {
                'q': '#blockchain',
                'limit': limit
            }
            
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            
            posts = resp.json().get('posts', [])
            logger.info(f"Found {len(posts)} blockchain posts")
            return posts
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error searching posts: {str(e)}")
            if e.response.status_code == 403:
                logger.error("Authentication failed. Please check your API credentials.")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching posts: {str(e)}")
            raise

    def like_post(self, uri: str, cid: str, repo: Optional[str] = None) -> dict:
        """Like a post on Bluesky.
        
        Args:
            uri (str): The URI of the post to like
            cid (str): The CID of the post to like
            repo (Optional[str]): The repository (DID) to like from. Defaults to the authenticated user's DID.
            
        Returns:
            dict: The API response containing the created like's URI and CID
        """
        url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
        if repo is None:
            repo = self.api_key  # This should be the DID (Decentralized Identifier)
            
        # Get current timestamp in the correct format for Bluesky
        from datetime import datetime, timezone
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
        
        try:
            resp = self.session.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.error(f"Bad request. Response: {e.response.text}")
            raise

    def search_and_like_blockchain(self, like_count: int = 1):
        """Search for blockchain-related posts and like them.
        
        Args:
            like_count (int): Number of posts to like (default: 1)
            
        Returns:
            list: Results of the like operations
        """
        try:
            logger.info(f"Searching for blockchain posts to like (count: {like_count})...")
            posts = self.search_blockchain_posts(limit=like_count)
            logger.info(f"Found {len(posts)} blockchain posts")
            
            results = []
            for i, post in enumerate(posts, 1):
                try:
                    uri = post.get('uri')
                    cid = post.get('cid')
                    if not uri or not cid:
                        logger.warning(f"Post {i} missing URI or CID, skipping")
                        continue
                        
                    logger.info(f"Liking post {i}/{len(posts)}: {uri}")
                    result = self.like_post(uri, cid)
                    results.append(result)
                    logger.info(f"Successfully liked post {i}")
                    
                    # Add a small delay between likes
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Failed to like post {i}: {str(e)}")
                    continue
                    
            logger.info(f"Completed liking {len(results)} posts")
            return results
            
        except Exception as e:
            logger.error(f"Error in search_and_like_blockchain: {str(e)}")
            raise
