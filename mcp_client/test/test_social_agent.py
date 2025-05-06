import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from mcp_client.agents.social_agent import SocialAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_telegram_posting():
    """Test Telegram posting functionality."""
    try:
        agent = SocialAgent()
        logger.info("Testing Telegram posting...")
        
        # Test process_and_post
        result = agent.process_and_post('telegram', {})
        logger.info(f"Telegram posting result: {result}")
        
        return result
    except Exception as e:
        logger.error(f"Error testing Telegram posting: {str(e)}")
        return False

def test_scheduling():
    """Test post scheduling functionality."""
    try:
        agent = SocialAgent()
        logger.info("Testing post scheduling...")
        
        # Schedule a post for 5 minutes from now
        schedule_time = (datetime.now() + timedelta(minutes=5)).isoformat()
        content = {
            'title': 'Test Post',
            'content': 'This is a test scheduled post',
            'url': 'https://example.com'
        }
        
        # Test scheduling for different platforms
        platforms = ['telegram', 'linkedin', 'bluesky', 'twitter']
        results = {}
        
        for platform in platforms:
            result = agent.schedule_post(platform, content, schedule_time)
            results[platform] = result
            logger.info(f"Scheduled {platform} post: {result}")
            
        return all(results.values())
    except Exception as e:
        logger.error(f"Error testing scheduling: {str(e)}")
        return False

def test_content_extraction():
    """Test content extraction functionality."""
    try:
        agent = SocialAgent()
        logger.info("Testing content extraction...")
        
        # Test with a sample URL
        url = "https://example.com"
        content = agent.extract_content(url)
        
        logger.info(f"Extracted content: {content}")
        return bool(content)
    except Exception as e:
        logger.error(f"Error testing content extraction: {str(e)}")
        return False

def test_status():
    """Test status reporting functionality."""
    try:
        agent = SocialAgent()
        logger.info("Testing status reporting...")
        
        status = agent.get_status()
        logger.info(f"Platform statuses: {status}")
        
        return bool(status)
    except Exception as e:
        logger.error(f"Error testing status: {str(e)}")
        return False

def main():
    """Run all tests."""
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("No .env file found")
            return
            
        load_dotenv(dotenv_path)
        logger.info(f"Loaded .env from: {dotenv_path}")
        
        # Run tests
        tests = {
            'Telegram Posting': test_telegram_posting,
            'Scheduling': test_scheduling,
            'Content Extraction': test_content_extraction,
            'Status Reporting': test_status
        }
        
        results = {}
        for test_name, test_func in tests.items():
            logger.info(f"\nRunning test: {test_name}")
            results[test_name] = test_func()
            
        # Print summary
        logger.info("\nTest Results Summary:")
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 