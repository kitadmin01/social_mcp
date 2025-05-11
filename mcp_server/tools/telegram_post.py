import os
import requests
import logging
from datetime import datetime
import telegram
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramPoster:
    def __init__(self):
        logger.info("Initializing TelegramPoster...")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_channel = os.getenv('TELEGRAM_CHANNEL')
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        
        # Log initialization details
        logger.info(f"Telegram Channel: {self.telegram_channel}")
        logger.info(f"Google Sheet ID: {self.sheet_id}")
        
        # Validate Telegram token
        if not self.telegram_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
            
        # Clean the token of any whitespace or special characters
        self.telegram_token = self.telegram_token.strip()
        logger.info(f"Token length: {len(self.telegram_token)}")
        logger.info(f"Token format: {self.telegram_token.count(':')} colon(s) found")
        
        if not self.telegram_token.count(':') == 1:
            logger.error(f"Invalid TELEGRAM_BOT_TOKEN format. Token: {self.telegram_token}")
            raise ValueError("Invalid TELEGRAM_BOT_TOKEN format. Should be in format 'BOT_ID:API_KEY'")
            
        # Initialize Telegram bot
        try:
            logger.info("Initializing Telegram bot...")
            self.bot = telegram.Bot(token=self.telegram_token)
            # Test the token by getting bot info
            bot_info = self.bot.get_me()
            logger.info(f"Telegram bot initialized successfully. Bot username: @{bot_info.username}")
            
            # Verify channel access
            try:
                # Try to get channel info
                chat_info = self.bot.get_chat(chat_id=self.telegram_channel)
                logger.info(f"Successfully accessed channel: {chat_info.title}")
            except Exception as e:
                logger.error(f"Failed to access channel. Please make sure the bot is an administrator of the channel. Error: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {str(e)}")
            raise
            
        # Initialize Google Sheets client
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, scope)
            self.gc = gspread.authorize(credentials)
            
            # Get the spreadsheet
            spreadsheet = self.gc.open_by_key(self.sheet_id)
            logger.info(f"Successfully opened spreadsheet: {spreadsheet.title}")
            
            # List all worksheets
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]
            logger.info(f"Available worksheets: {', '.join(worksheet_names)}")
            
            # Find worksheet case-insensitively
            target_worksheet = None
            for ws in worksheets:
                if ws.title.lower() == 'sheet2':
                    target_worksheet = ws
                    break
            
            if target_worksheet:
                self.sheet = target_worksheet
                logger.info(f"Using existing worksheet: {self.sheet.title}")
                
                # Verify required columns exist
                headers = self.sheet.row_values(1)
                required_columns = ['tele_urls', 'status', 'error', 'last_update_ts']
                missing_columns = [col for col in required_columns if col.lower() not in [h.lower() for h in headers]]
                
                if missing_columns:
                    logger.warning(f"Missing columns in worksheet: {', '.join(missing_columns)}")
                    logger.info("Adding missing columns...")
                    # Add missing columns
                    for col in missing_columns:
                        col_index = len(headers) + 1
                        self.sheet.update_cell(1, col_index, col)
                        headers.append(col)
                    logger.info("Added missing columns to worksheet")
            else:
                logger.error("No worksheet matching 'sheet2' (case-insensitive) found")
                raise ValueError("Required worksheet not found")
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            raise

    def get_pending_urls(self) -> List[Dict[str, Any]]:
        """Get URLs from Google Sheet that need to be processed.
        
        Returns:
            List[Dict[str, Any]]: List of URLs with their row numbers
        """
        try:
            logger.info("Fetching pending URLs from Google Sheet")
            # Get all records
            records = self.sheet.get_all_records()
            pending_urls = []
            
            # Find rows where status is empty
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
                if not record.get('status') and record.get('tele_urls'):
                    pending_urls.append({
                        'row': i,
                        'url': record['tele_urls']
                    })
            
            logger.info(f"Found {len(pending_urls)} pending URLs")
            return pending_urls
            
        except Exception as e:
            logger.error(f"Error getting pending URLs: {str(e)}")
            return []

    def get_blog_content(self, url: str) -> Dict[str, Any]:
        """Get content from blog URL.
        
        Args:
            url (str): URL of the blog post
            
        Returns:
            Dict[str, Any]: Blog post content with title and text
        """
        try:
            logger.info(f"Fetching content from URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.find('h1')
            title_text = title.get_text().strip() if title else "Untitled"
            
            # Extract content
            content = soup.find('article') or soup.find('div', class_='entry-content')
            content_text = content.get_text().strip() if content else ""
            
            return {
                'title': title_text,
                'content': content_text,
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Error getting blog content: {str(e)}")
            return {}

    def format_telegram_message(self, post: Dict[str, Any]) -> str:
        """Format blog post for Telegram message.
        
        Args:
            post (Dict[str, Any]): Blog post data
            
        Returns:
            str: Formatted message for Telegram
        """
        try:
            message = f"📝 *{post['title']}*\n\n"
            
            # Truncate content if too long
            content = post['content']
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            message += f"{content}\n\n"
            message += f"🔗 [Read More]({post['url']})"
            
            logger.info(f"Formatted message for post: {post['title']}")
            return message
        except Exception as e:
            logger.error(f"Error formatting message: {str(e)}")
            return ""

    def update_sheet_status(self, row: int, status: str, error: str = ""):
        """Update the status and error columns in the Google Sheet.
        
        Args:
            row (int): Row number to update
            status (str): Status to set
            error (str): Error message if any
        """
        try:
            # Update status
            self.sheet.update_cell(row, self.sheet.find('status').col, status)
            
            # Update error if provided
            if error:
                self.sheet.update_cell(row, self.sheet.find('error').col, error)
            
            # Update timestamp
            self.sheet.update_cell(row, self.sheet.find('last_update_ts').col, 
                                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            logger.info(f"Updated sheet row {row} with status: {status}")
        except Exception as e:
            logger.error(f"Error updating sheet status: {str(e)}")

    def post_to_telegram(self, message: str) -> bool:
        """Post message to Telegram channel."""
        try:
            logger.info(f"Attempting to post to Telegram channel: {self.telegram_channel}")
            
            # First try to get chat info to verify access
            try:
                chat_info = self.bot.get_chat(chat_id=self.telegram_channel)
                logger.info(f"Successfully accessed channel: {chat_info.title}")
            except telegram.error.BadRequest as e:
                logger.error(f"Failed to access channel. Please verify: 1) Channel name is correct 2) Bot is an administrator 3) Channel exists. Error: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error accessing channel: {str(e)}")
                return False
            
            # Now try to send the message
            try:
                result = self.bot.send_message(
                    chat_id=self.telegram_channel,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                logger.info(f"Successfully posted to Telegram. Message ID: {result.message_id}")
                return True
            except telegram.error.BadRequest as e:
                logger.error(f"Failed to send message. Bot might not have permission to post. Error: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error sending message: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error posting to Telegram: {str(e)}")
            return False

    def process_and_post(self, limit: int = 5):
        """Get URLs from sheet and post them to Telegram.
        
        Args:
            limit (int): Maximum number of URLs to process
        """
        try:
            logger.info(f"Starting process_and_post with limit: {limit}")
            pending_urls = self.get_pending_urls()[:limit]
            
            if not pending_urls:
                logger.info("No pending URLs found to process")
                return
                
            for url_data in pending_urls:
                try:
                    # Get blog content
                    post = self.get_blog_content(url_data['url'])
                    if not post:
                        error_msg = "Failed to fetch blog content"
                        self.update_sheet_status(url_data['row'], "error", error_msg)
                        continue
                        
                    # Format and post to Telegram
                    message = self.format_telegram_message(post)
                    if not message:
                        error_msg = "Failed to format message"
                        self.update_sheet_status(url_data['row'], "error", error_msg)
                        continue
                        
                    # Post to Telegram
                    if self.post_to_telegram(message):
                        self.update_sheet_status(url_data['row'], "complete")
                    else:
                        error_msg = "Failed to post to Telegram"
                        self.update_sheet_status(url_data['row'], "error", error_msg)
                        
                    time.sleep(5)  # Add delay between posts
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing URL {url_data['url']}: {error_msg}")
                    self.update_sheet_status(url_data['row'], "error", error_msg)
                
            logger.info(f"Successfully processed {len(pending_urls)} URLs")
            
        except Exception as e:
            logger.error(f"Error in process_and_post: {str(e)}") 