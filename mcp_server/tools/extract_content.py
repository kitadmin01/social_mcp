import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
import time

logger = logging.getLogger(__name__)

class ExtractContent:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

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
            # Add retry logic for requests
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    response = self.session.get(url, timeout=30)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    time.sleep(retry_delay * (attempt + 1))
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find the main article content with more specific selectors
            selectors = [
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
                '.news-content'
            ]
            
            # Try each selector
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    # Get text content and clean it
                    text = element.get_text(separator=' ', strip=True)
                    # Remove extra whitespace
                    text = ' '.join(text.split())
                    if len(text) > 100:
                        return text
            
            # If no specific content found, try to get the main content area
            main_content = soup.select_one('main') or soup.select_one('#main') or soup.select_one('.main')
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())
                if len(text) > 100:
                    return text
            
            # Fallback to body text, but exclude navigation and footer
            body = soup.body
            if body:
                # Remove navigation and footer
                for element in body.select('nav, footer, header, .nav, .footer, .header'):
                    element.decompose()
                
                text = body.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())
                if len(text) > 100:
                    return text
            
            logger.warning(f"Could not find sufficient content from URL: {url}")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return "" 