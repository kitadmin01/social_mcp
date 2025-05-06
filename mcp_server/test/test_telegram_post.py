import os
import logging
from dotenv import load_dotenv, find_dotenv
from mcp_server.tools.telegram_post import TelegramPoster

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Load environment variables
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("No .env file found")
            return
            
        load_dotenv(dotenv_path)
        logger.info(f"Loaded .env from: {dotenv_path}")
        
        # Check required environment variables
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHANNEL',
            'GOOGLE_SHEET_ID',
            'GOOGLE_SHEETS_CREDENTIALS'
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return
            
        # Initialize TelegramPoster
        logger.info("Initializing TelegramPoster...")
        tg_poster = TelegramPoster()
        
        # Test getting pending URLs
        logger.info("Testing get_pending_urls()...")
        pending_urls = tg_poster.get_pending_urls()
        logger.info(f"Found {len(pending_urls)} pending URLs")
        
        # Test processing and posting
        logger.info("Starting to process and post URLs...")
        tg_poster.process_and_post(limit=2)  # Process only 2 URLs for testing
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 