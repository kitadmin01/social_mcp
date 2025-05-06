import logging
from typing import Dict, Any, List
from mcp_server.tools.telegram_post import TelegramPoster
from mcp_server.tools.linkedin import LinkedIn
from mcp_server.tools.bsky import Bluesky
from mcp_server.tools.post_tweets import Twitter
from mcp_server.tools.extract_content import ContentExtractor
from mcp_server.tools.schedule_post import PostScheduler

logger = logging.getLogger(__name__)

class SocialAgent:
    def __init__(self):
        """Initialize the SocialAgent with all required tools."""
        self.telegram = TelegramPoster()
        self.linkedin = LinkedIn()
        self.bluesky = Bluesky()
        self.twitter = Twitter()
        self.content_extractor = ContentExtractor()
        self.scheduler = PostScheduler()
        
    def process_and_post(self, platform: str, content: Dict[str, Any]) -> bool:
        """Process and post content to specified platform.
        
        Args:
            platform (str): Target platform ('telegram', 'linkedin', 'bluesky', 'twitter')
            content (Dict[str, Any]): Content to post
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if platform.lower() == 'telegram':
                return self.telegram.process_and_post(limit=1)
            elif platform.lower() == 'linkedin':
                return self.linkedin.post(content)
            elif platform.lower() == 'bluesky':
                return self.bluesky.post(content)
            elif platform.lower() == 'twitter':
                return self.twitter.post(content)
            else:
                logger.error(f"Unsupported platform: {platform}")
                return False
        except Exception as e:
            logger.error(f"Error posting to {platform}: {str(e)}")
            return False
            
    def schedule_post(self, platform: str, content: Dict[str, Any], schedule_time: str) -> bool:
        """Schedule a post for later.
        
        Args:
            platform (str): Target platform
            content (Dict[str, Any]): Content to post
            schedule_time (str): Scheduled time in ISO format
            
        Returns:
            bool: True if successfully scheduled
        """
        return self.scheduler.schedule(platform, content, schedule_time)
        
    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL.
        
        Args:
            url (str): URL to extract content from
            
        Returns:
            Dict[str, Any]: Extracted content
        """
        return self.content_extractor.extract(url)
        
    def run(self):
        """Main execution loop for the agent."""
        try:
            # Process scheduled posts
            scheduled_posts = self.scheduler.get_due_posts()
            for post in scheduled_posts:
                self.process_and_post(post['platform'], post['content'])
                
            # Process any other tasks
            # Add your custom logic here
            
        except Exception as e:
            logger.error(f"Error in SocialAgent run loop: {str(e)}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all platforms.
        
        Returns:
            Dict[str, Any]: Status information for each platform
        """
        return {
            'telegram': self.telegram.get_status() if hasattr(self.telegram, 'get_status') else None,
            'linkedin': self.linkedin.get_status() if hasattr(self.linkedin, 'get_status') else None,
            'bluesky': self.bluesky.get_status() if hasattr(self.bluesky, 'get_status') else None,
            'twitter': self.twitter.get_status() if hasattr(self.twitter, 'get_status') else None
        } 