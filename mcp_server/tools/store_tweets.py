# Placeholder for storing tweets

import json
from datetime import datetime
from common.google_sheets import GoogleSheetsClient

class StoreTweets:
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client

    def store_llm_tweets(self, row_id: int, tweets: list):
        now = datetime.utcnow().isoformat()
        tweet_objs = [
            {"index": i+1, "text": tweet, "gen_ts": now}
            for i, tweet in enumerate(tweets)
        ]
        tweets_json = json.dumps(tweet_objs, ensure_ascii=False)
        self.sheets_client.store_tweets(row_id, tweets_json)

