import os
import logging
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LinkedInAPI:
    def __init__(self):
        self.client_id = os.getenv('LINKEDIN_CLIENT_ID')
        self.client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        self.person_urn = os.getenv('LINKEDIN_PERSON_URN')
        self.org_urn = os.getenv('LINKEDIN_ORG_URN')
        self.api_base = 'https://api.linkedin.com/v2'
        if not all([self.client_id, self.client_secret, self.access_token]):
            raise ValueError('Missing LinkedIn API credentials in environment variables')
        logger.info('LinkedInAPI initialized with API credentials')

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json',
        }

    def create_post(self, text):
        """Create a post on LinkedIn using the API. Posts as a company if LINKEDIN_ORG_URN is set, otherwise as the user."""
        author_urn = self.org_urn if self.org_urn else self.person_urn
        logger.info(f"Posting as author: {author_urn}")
        url = f'{self.api_base}/ugcPosts'
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        logger.info(f"Posting to LinkedIn API: {payload}")
        response = requests.post(url, headers=self._headers(), json=payload)
        if response.status_code == 201:
            logger.info("Successfully created LinkedIn post via API")
            return {'status': 'success', 'message': 'Post created successfully', 'id': response.json().get('id')}
        else:
            logger.error(f"LinkedIn API post failed: {response.status_code} {response.text}")
            return {'status': 'error', 'message': response.text}

    def cleanup(self):
        pass  # No cleanup needed for API approach 