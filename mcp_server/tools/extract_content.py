import asyncio
import logging
import time
import random
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class ExtractContent:
    def __init__(self):
        self.ua = UserAgent()
        self.browser = None
        self.context = None
        self.playwright = None

    async def init_browser(self):
        """Initialize the browser if not already initialized."""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins',
                    '--disable-site-isolation-trials',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self.ua.random,
                java_script_enabled=True,
                ignore_https_errors=True,
                bypass_csp=True
            )
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)

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

    def get_site_specific_selectors(self, url: str) -> list:
        """Get site-specific selectors based on the URL."""
        domain = urlparse(url).netloc.lower()
        
        selectors = {
            'cointelegraph.com': [
                '.post__content',
                '.post__content-wrapper',
                'article',
                '.article__content',
                '[itemprop="articleBody"]',
                '.post-content',
                '.article-text'
            ],
            'crypto.news': [
                '.article-content',
                '.post-content',
                'article',
                '.entry-content',
                '[itemprop="articleBody"]',
                '.content-area'
            ],
            'analytickit.com': [
                '.post-content',
                '.entry-content',
                'article',
                '.article-content',
                '[itemprop="articleBody"]',
                '.content'
            ],
            'default': [
                'article',
                '.article',
                '.post-content',
                '.entry-content',
                'main',
                '.content',
                '#content',
                '.post',
                '.article-content',
                '.story-content',
                '.article-body',
                '.post-body',
                '.entry',
                '.blog-post',
                '.news-content',
                '[itemprop="articleBody"]',
                '.article-text',
                '.article-body-text',
                '.article-content-text'
            ]
        }
        
        return selectors.get(domain, selectors['default'])

    async def wait_for_content(self, page, selectors: list) -> bool:
        """Wait for content to load using multiple strategies."""
        try:
            # Wait for network to be idle
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Wait for any of the selectors to be present
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    return True
                except TimeoutError:
                    continue
            
            # If no selectors found, wait for body to be present
            await page.wait_for_selector('body', timeout=5000)
            return True
            
        except TimeoutError:
            logger.warning("Timeout waiting for content")
            return False
        except Exception as e:
            logger.warning(f"Error waiting for content: {str(e)}")
            return False

    async def extract(self, url: str) -> str:
        if not self.is_valid_url(url):
            logger.error(f"Invalid URL provided: {url}")
            return ""
            
        logger.info(f"Extracting content from valid URL: {url}")
        try:
            # Initialize browser if needed
            await self.init_browser()
            
            # Create a new page
            page = await self.context.new_page()
            
            # Set extra headers
            await page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'DNT': '1'
            })
            
            # Get site-specific selectors
            selectors = self.get_site_specific_selectors(url)
            
            # Navigate to the URL with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    if response and response.ok:
                        # Wait for content to load
                        if await self.wait_for_content(page, selectors):
                            break
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
            
            # Additional wait for dynamic content
            await asyncio.sleep(3)
            
            # Get the page content
            content = await page.content()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Try each selector
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    # Try each element found with this selector
                    for element in elements:
                        # Remove unwanted elements
                        for unwanted in element.select('script, style, .ads, .advertisement, .social-share, .comments, .related-posts, .newsletter, .sidebar, .widget, .share-buttons, .author-bio, .recommended-posts'):
                            unwanted.decompose()
                        
                        # Get text content
                        text = element.get_text(separator=' ', strip=True)
                        text = ' '.join(text.split())
                        
                        # Check if we have enough content
                        if len(text) > 100:
                            logger.info(f"Found content using selector: {selector}")
                            return text
            
            # If no specific content found, try to get the main content area
            main_content = soup.select_one('main') or soup.select_one('#main') or soup.select_one('.main')
            
            if main_content:
                # Remove unwanted elements
                for unwanted in main_content.select('script, style, .ads, .advertisement, .social-share, .comments, .related-posts, .newsletter, .sidebar, .widget, .share-buttons, .author-bio, .recommended-posts'):
                    unwanted.decompose()
                
                text = main_content.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())
                if len(text) > 100:
                    logger.info("Found content in main content area")
                    return text
            
            # Fallback to body text, but exclude navigation and footer
            body = soup.body
            if body:
                # Remove unwanted elements
                for unwanted in body.select('nav, footer, header, .nav, .footer, .header, script, style, .ads, .advertisement, .social-share, .comments, .related-posts, .newsletter, .sidebar, .widget, .share-buttons, .author-bio, .recommended-posts'):
                    unwanted.decompose()
                
                text = body.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())
                if len(text) > 100:
                    logger.info("Found content in body")
                    return text
            
            logger.warning(f"Could not find sufficient content from URL: {url}")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return ""
        finally:
            # Close the page
            if 'page' in locals():
                await page.close()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop() 