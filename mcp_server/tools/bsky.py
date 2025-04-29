# Placeholder for posting to Bluesky via API

import os
import requests
from typing import Optional

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
        url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
        if repo is None:
            repo = self.api_key
        payload = {
            "repo": repo,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text
            }
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def search_blockchain_posts(self, limit: int = 5) -> list:
        url = 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=%23blockchain'
        resp = self.session.get(url)
        resp.raise_for_status()
        posts = resp.json().get('posts', [])
        return posts[:limit]

    def like_post(self, uri: str, cid: str, repo: Optional[str] = None) -> dict:
        url = 'https://bsky.social/xrpc/com.atproto.repo.createRecord'
        if repo is None:
            repo = self.api_key
        payload = {
            "repo": repo,
            "collection": "app.bsky.feed.like",
            "record": {
                "$type": "app.bsky.feed.like",
                "subject": {"uri": uri, "cid": cid}
            }
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def search_and_like_blockchain(self, like_count: int = 1):
        posts = self.search_blockchain_posts(limit=like_count)
        results = []
        for post in posts:
            uri = post.get('uri')
            cid = post.get('cid')
            if uri and cid:
                result = self.like_post(uri, cid)
                results.append(result)
        return results
