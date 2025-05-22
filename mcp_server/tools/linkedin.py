import os
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from linkedin_api import Linkedin
from typing import List, Dict, Any
from datetime import datetime
from common.llm_orchestrator import LLMOrchestrator
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LinkedInPoster:
    def __init__(self):
        logger.info("Initializing LinkedInPoster...")
        self.linkedin_email = os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        self.company_id = os.getenv('LINKEDIN_COMPANY_ID', '80256853')  # Default to the provided company ID
        
        # Initialize LLM orchestrator
        self.llm = LLMOrchestrator()
        
        # Validate LinkedIn credentials
        if not self.access_token:
            logger.error("LINKEDIN_ACCESS_TOKEN not found in environment variables")
            raise ValueError("LinkedIn credentials are required")
            
        # Initialize Google Sheets client
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, scope)
            self.gc = gspread.authorize(credentials)
            
            # Get the spreadsheet
            spreadsheet = self.gc.open_by_key(self.sheet_id)
            logger.info(f"Successfully opened spreadsheet: {spreadsheet.title}")
            
            # Get Sheet1
            self.sheet = spreadsheet.worksheet('Sheet1')
            logger.info(f"Using worksheet: {self.sheet.title}")
            
            # Verify required columns exist
            headers = self.sheet.row_values(1)
            required_columns = ['url', 'status', 'error', 'last_update_ts']
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
            
            # Find rows where status is "pending"
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
                if record.get('status') == 'pending' and record.get('url'):
                    pending_urls.append({
                        'row': i,
                        'url': record['url']
                    })
            
            logger.info(f"Found {len(pending_urls)} pending URLs")
            return pending_urls
            
        except Exception as e:
            logger.error(f"Error getting pending URLs: {str(e)}")
            return []

    async def generate_linkedin_content(self, url: str) -> str:
        """Generate LinkedIn post content using LLM.
        
        Args:
            url (str): URL of the content to post
            
        Returns:
            str: Generated LinkedIn post content
        """
        try:
            prompt = f"""Create an engaging LinkedIn post about this content: {url}
            The post should:
            1. Be professional and insightful
            2. Include a brief summary of the key points
            3. End with a call to action
            4. Be under 1300 characters
            5. Include relevant hashtags
            """
            
            content = await self.llm.generate_content(prompt)
            logger.info("Generated LinkedIn post content successfully")
            return content
            
        except Exception as e:
            logger.error(f"Error generating LinkedIn content: {str(e)}")
            raise

    def update_sheet_status(self, row: int, status: str, error: str = ""):
        """Update the status of a URL in the Google Sheet.
        
        Args:
            row (int): Row number to update
            status (str): New status
            error (str, optional): Error message if any
        """
        try:
            # Get current timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update status and timestamp
            self.sheet.update_cell(row, self.sheet.find('status').col, status)
            self.sheet.update_cell(row, self.sheet.find('last_update_ts').col, timestamp)
            
            # Update linkedin_result column
            linkedin_result = "success" if status == "posted" else f"error: {error}"
            self.sheet.update_cell(row, self.sheet.find('linkedin_result').col, linkedin_result)
            
            if error:
                self.sheet.update_cell(row, self.sheet.find('error').col, error)
                
            logger.info(f"Updated sheet status for row {row}: {status}")
            
        except Exception as e:
            logger.error(f"Error updating sheet status: {str(e)}")

    def post_to_linkedin(self, content: str, url: str) -> bool:
        """Post content to LinkedIn using v2 API.
        
        Args:
            content (str): Post content
            url (str): URL to include in the post
            
        Returns:
            bool: True if post was successful, False otherwise
        """
        try:
            # Add URL to the content
            full_content = f"{content}\n\n{url}"
            
            # Prepare the API request
            api_url = 'https://api.linkedin.com/v2/ugcPosts'
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'X-Restli-Protocol-Version': '2.0.0',
                'Content-Type': 'application/json'
            }
            
            # Prepare the post data with company URN
            post_data = {
                "author": f"urn:li:company:{self.company_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": full_content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Make the API request
            response = requests.post(api_url, headers=headers, json=post_data)
            response.raise_for_status()
            
            logger.info("Successfully posted to LinkedIn")
            return True
            
        except Exception as e:
            logger.error(f"Error posting to LinkedIn: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response.text}")
            return False

    async def process_and_post(self, limit: int = 5):
        """Process pending URLs and post to LinkedIn.
        
        Args:
            limit (int, optional): Maximum number of URLs to process. Defaults to 5.
        """
        try:
            # Get pending URLs
            pending_urls = self.get_pending_urls()
            
            # Process up to limit URLs
            for url_data in pending_urls[:limit]:
                try:
                    row = url_data['row']
                    url = url_data['url']
                    
                    # Generate content
                    content = await self.generate_linkedin_content(url)
                    
                    # Post to LinkedIn
                    if self.post_to_linkedin(content, url):
                        self.update_sheet_status(row, 'posted')
                    else:
                        self.update_sheet_status(row, 'error', 'Failed to post to LinkedIn')
                        
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {str(e)}")
                    self.update_sheet_status(row, 'error', str(e))
                    
        except Exception as e:
            logger.error(f"Error in process_and_post: {str(e)}")
            raise 