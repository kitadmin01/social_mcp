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
        rows = self.get_rows()
        logger.info(f"Found {len(rows)} total rows in sheet")
        
        pending_rows = []
        for row in rows:
            url = row.get('url', '')
            status = row.get('status', '').lower()
            
            if status == 'pending':
                logger.info(f"Found pending row {row.get('id')} with URL: {url}")
                if self.is_valid_url(url):
                    logger.info(f"Valid URL found: {url}")
                    pending_rows.append(row)
                else:
                    logger.warning(f"Invalid URL in pending row {row.get('id')}: {url}")
                    # Mark invalid URLs as error
                    self.update_row(row['id'], {
                        "status": "error",
                        "processing_ts": datetime.utcnow().isoformat(),
                        "retry_count_content": 0,
                        "content_ts": datetime.utcnow().isoformat()
                    })
        
        logger.info(f"Returning {len(pending_rows)} valid pending URLs")
        return pending_rows

    def update_row(self, row_id: int, updates: Dict[str, Any]):
        # Find the row index by id (assuming 'id' is unique and in the first column)
        cell = self.worksheet.find(str(row_id))
        row_idx = cell.row
        for col, value in updates.items():
            if col in COLUMNS:
                col_idx = COLUMNS.index(col) + 1
                self.worksheet.update_cell(row_idx, col_idx, value)
        # Always update last_update_ts
        self.worksheet.update_cell(row_idx, COLUMNS.index('last_update_ts') + 1, datetime.utcnow().isoformat())

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
