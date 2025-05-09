import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from common.google_sheets import GoogleSheetsClient
from mcp_server.tools.extract_content import ExtractContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TestExtractContent:
    def __init__(self):
        # Initialize Google Sheets client just to read URLs
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                      "google_sheets_credentials.json")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id:
            raise ValueError("GOOGLE_SHEET_ID environment variable is not set")
            
        self.sheets = GoogleSheetsClient(credentials_path, sheet_id)
        self.extractor = ExtractContent()

    async def test_url(self, url: str) -> bool:
        """Test content extraction for a single URL."""
        try:
            logger.info(f"\nTesting URL: {url}")
            content = await self.extractor.extract(url)
            
            if not content:
                logger.error(f"Failed to extract content from URL: {url}")
                return False
                
            # Log success and content length
            logger.info(f"Successfully extracted content from {url}")
            logger.info(f"Content length: {len(content)} chars")
            logger.info(f"First 200 chars: {content[:200]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error testing URL {url}: {str(e)}")
            return False

    async def run_tests(self):
        """Run tests for all URLs in Sheet2."""
        try:
            # Get Sheet2
            sheet2 = self.sheets.sheet.worksheet("Sheet2")
            if not sheet2:
                logger.error("Sheet2 not found")
                return
                
            # Get all records from Sheet2
            records = sheet2.get_all_records()
            
            # Track results
            total_urls = 0
            successful = 0
            failed = 0
            failed_urls = []
            
            # Test each URL
            for record in records:
                url = record.get('tele_urls')
                if url and url.strip():
                    total_urls += 1
                    success = await self.test_url(url)
                    if success:
                        successful += 1
                    else:
                        failed += 1
                        failed_urls.append(url)
                        
            # Log summary
            logger.info("\nTest Summary:")
            logger.info(f"Total URLs tested: {total_urls}")
            logger.info(f"Successful extractions: {successful}")
            logger.info(f"Failed extractions: {failed}")
            logger.info(f"Success rate: {(successful/total_urls)*100:.2f}%")
            
            if failed_urls:
                logger.info("\nFailed URLs:")
                for url in failed_urls:
                    logger.info(f"- {url}")
            
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
        finally:
            # Clean up browser resources
            await self.extractor.cleanup()

async def main():
    tester = TestExtractContent()
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main()) 