from playwright.async_api import async_playwright
from urllib.parse import urlparse
import logging
import asyncio

logger = logging.getLogger(__name__)

class ExtractContent:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    async def initialize(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )

    async def cleanup(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

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

    async def extract(self, url: str) -> str:
        if not self.is_valid_url(url):
            logger.error(f"Invalid URL provided: {url}")
            return ""
            
        logger.info(f"Extracting content from valid URL: {url}")
        try:
            await self.initialize()
            page = await self.context.new_page()
            await page.goto(url, wait_until="networkidle")
            # Wait for content to load
            await asyncio.sleep(2)
            
            # Try to get the main content
            content = await page.evaluate("""
                () => {
                    // Try to find the main article content
                    const article = document.querySelector('article') || 
                                  document.querySelector('.article') ||
                                  document.querySelector('.post-content') ||
                                  document.querySelector('.entry-content') ||
                                  document.querySelector('main');
                    
                    if (article) {
                        return article.innerText;
                    }
                    
                    // Fallback to body text
                    return document.body.innerText;
                }
            """)
            
            await page.close()
            
            if not content or len(content.strip()) < 100:
                logger.warning(f"Extracted content too short from URL: {url}")
                return ""
                
            return content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return "" 