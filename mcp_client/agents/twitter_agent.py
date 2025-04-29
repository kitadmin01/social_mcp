from mcp_server.tools.post_tweets import TwitterPlaywright

class TwitterAgent:
    def __init__(self):
        self.playwright = TwitterPlaywright()

    def post_tweet(self, tweet):
        print(f"Posting tweet: {tweet}")
        self.playwright.post_tweet(tweet)

    def like_blockchain_tweets(self, like_count=5):
        print(f"Liking {like_count} #blockchain tweets on Twitter...")
        self.playwright.like_blockchain_tweets(like_count=like_count) 