# Placeholder for Google Sheets integration utilities

import gspread
from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLUMNS = [
    'id', 'url', 'status', 'Medium', 'processing_ts', 'content_ts', 'retry_count_content',
    'generate_ts', 'retry_count_generate', 'tweets', 'store_ts', 'twitter_result',
    'retry_count_post_twitter', 'bsky_result', 'retry_count_post_bsky', 'engage_ts',
    'schedule_ts', 'retry_count_schedule', 'last_update_ts'
]

class GoogleSheetsClient:
    def __init__(self, credentials_json: str, sheet_id: str, worksheet_name: str = 'Sheet1'):
        self.gc = gspread.service_account(filename=credentials_json)
        self.sheet = self.gc.open_by_key(sheet_id)
        self.worksheet = self.sheet.worksheet(worksheet_name)

    def get_rows(self) -> List[Dict[str, Any]]:
        records = self.worksheet.get_all_records()
        return records

    def is_valid_url(self, url: str) -> bool:
        if not isinstance(url, str):
            logger.warning(f"URL is not a string: {url}")
            return False
        if url.lower() in ['pending', 'in_progress', 'complete', 'error']:
            logger.warning(f"URL is a status value: {url}")
            return False
        try:
            result = urlparse(url)
            is_valid = all([result.scheme, result.netloc])
            if not is_valid:
                logger.warning(f"Invalid URL format: {url}")
            return is_valid
        except Exception as e:
            logger.warning(f"URL parsing error for {url}: {str(e)}")
            return False

    def get_pending_urls(self) -> List[Dict[str, Any]]:
        """Get URLs from Google Sheet that need to be processed.
        
        Returns:
            List[Dict[str, Any]]: List of URLs with their row numbers
        """
        try:
            logger.info("Fetching pending URLs from Google Sheet")
            # Get all records from the worksheet
            records = self.worksheet.get_all_records()
            pending_urls = []
            
            # Find rows where status is empty or pending
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
                if (not record.get('status') or record.get('status').lower() == 'pending') and record.get('url'):
                    # Create a properly formatted row with ID
                    formatted_row = {
                        'id': i,  # Use row number as ID
                        'url': record.get('url', ''),
                        'status': record.get('status', ''),
                        'title': record.get('title', ''),
                        'content': record.get('content', ''),
                        'tweets': record.get('tweets', ''),
                        'retry_count_content': record.get('retry_count_content', '0'),
                        'retry_count_generate': record.get('retry_count_generate', '0'),
                        'retry_count_post': record.get('retry_count_post', '0'),
                        'retry_count_bsky': record.get('retry_count_bsky', '0'),
                        'retry_count_telegram': record.get('retry_count_telegram', '0'),
                        'processing_ts': record.get('processing_ts', ''),
                        'content_ts': record.get('content_ts', ''),
                        'generate_ts': record.get('generate_ts', ''),
                        'post_ts': record.get('post_ts', ''),
                        'bsky_ts': record.get('bsky_ts', ''),
                        'telegram_ts': record.get('telegram_ts', ''),
                        'last_update_ts': record.get('last_update_ts', '')
                    }
                    pending_urls.append(formatted_row)
            
            logger.info(f"Found {len(pending_urls)} pending URLs")
            return pending_urls
            
        except Exception as e:
            logger.error(f"Error getting pending URLs: {str(e)}")
            return []

    def update_row(self, row_id: int, updates: Dict[str, Any]):
        """Update specific columns in a row.
        
        Args:
            row_id (int): The row number to update (1-based index)
            updates (Dict[str, Any]): Dictionary of column names and values to update
        """
        try:
            # Get the header row to find column indices
            headers = self.worksheet.row_values(1)
            
            # Update each column
            for col, value in updates.items():
                if col in headers:
                    col_idx = headers.index(col) + 1  # Convert to 1-based index
                    self.worksheet.update_cell(row_id, col_idx, str(value))
                else:
                    logger.warning(f"Column '{col}' not found in headers")
            
            # Always update last_update_ts
            if 'last_update_ts' in headers:
                last_update_idx = headers.index('last_update_ts') + 1
                self.worksheet.update_cell(row_id, last_update_idx, datetime.utcnow().isoformat())
            
            logger.info(f"Updated row {row_id} with {len(updates)} fields")
            
        except Exception as e:
            logger.error(f"Error updating row {row_id}: {str(e)}")
            raise

    def store_tweets(self, row_id: int, tweets: Any):
        self.update_row(row_id, {
            'tweets': str(tweets),
            'store_ts': datetime.utcnow().isoformat(),
            'status': 'tweets_stored'
        })

    def store_result(self, row_id: int, platform: str, result: str):
        col = f'{platform.lower()}_result'
        if col in COLUMNS:
            self.update_row(row_id, {col: result})

    def update_status(self, row_id: int, status: str):
        self.update_row(row_id, {'status': status})
 